from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction import Extraction, ExtractionStatus
from app.models.project import Project, ProjectStatus
from app.models.source_document import SourceDocument, SourceDocumentStatus


async def start_extraction(
    db: AsyncSession,
    document: SourceDocument,
) -> Extraction:
    result = await db.execute(
        select(Extraction).where(
            Extraction.source_document_id == document.id,
            Extraction.status.in_([
                ExtractionStatus.PENDING,
                ExtractionStatus.PROCESSING,
                ExtractionStatus.COMPLETED,
            ]),
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una extracción activa para este documento",
        )

    extraction = Extraction(
        source_document_id=document.id,
        content="",
        status=ExtractionStatus.PENDING,
    )
    db.add(extraction)

    document.set_status(SourceDocumentStatus.EXTRACTING)

    project_result = await db.execute(
        select(Project).where(Project.id == document.project_id)
    )
    project = project_result.scalar_one()
    if ProjectStatus.is_valid_transition(project.status, ProjectStatus.EXTRACTING):
        project.set_status(ProjectStatus.EXTRACTING)

    await db.commit()
    await db.refresh(extraction)
    return extraction


async def get_extraction(
    db: AsyncSession,
    extraction_id: str,
) -> Extraction:
    result = await db.execute(
        select(Extraction).where(Extraction.id == extraction_id)
    )
    extraction = result.scalar_one_or_none()
    if extraction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracción no encontrada",
        )
    return extraction


async def retry_extraction(
    db: AsyncSession,
    extraction: Extraction,
) -> Extraction:
    if extraction.status != ExtractionStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden reintentar extracciones en estado fallido",
        )

    extraction.status = ExtractionStatus.PENDING
    extraction.error_message = None
    extraction.content = ""

    doc_result = await db.execute(
        select(SourceDocument).where(SourceDocument.id == extraction.source_document_id)
    )
    document = doc_result.scalar_one()
    document.set_status(SourceDocumentStatus.EXTRACTING)

    project_result = await db.execute(
        select(Project).where(Project.id == document.project_id)
    )
    project = project_result.scalar_one()
    if ProjectStatus.is_valid_transition(project.status, ProjectStatus.EXTRACTING):
        project.set_status(ProjectStatus.EXTRACTING)

    await db.commit()
    await db.refresh(extraction)
    return extraction


async def extract_all_for_project(
    db: AsyncSession,
    project: Project,
) -> dict:
    if project.status not in (ProjectStatus.DRAFT, ProjectStatus.EXTRACTING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"El proyecto no se puede extraer (estado actual: {project.status})"
            ),
        )

    result = await db.execute(
        select(SourceDocument).where(SourceDocument.project_id == project.id)
    )
    all_documents = list(result.scalars().all())

    enqueued = 0
    skipped = 0
    retried = 0

    for document in all_documents:
        existing_result = await db.execute(
            select(Extraction).where(
                Extraction.source_document_id == document.id,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing is None:
            extraction = Extraction(
                source_document_id=document.id,
                content="",
                status=ExtractionStatus.PENDING,
            )
            db.add(extraction)
            document.set_status(SourceDocumentStatus.EXTRACTING)
            enqueued += 1

        elif existing.status == ExtractionStatus.FAILED:
            existing.status = ExtractionStatus.PENDING
            existing.error_message = None
            existing.content = ""
            document.set_status(SourceDocumentStatus.EXTRACTING)
            retried += 1

        elif existing.status in (
            ExtractionStatus.PENDING,
            ExtractionStatus.PROCESSING,
            ExtractionStatus.COMPLETED,
        ):
            skipped += 1

    if enqueued > 0 or retried > 0:
        project.set_status(ProjectStatus.EXTRACTING)
    await db.commit()

    return {
        "project_id": str(project.id),
        "total_documents": len(all_documents),
        "enqueued": enqueued,
        "retried": retried,
        "skipped": skipped,
        "project_status": project.status,
    }
