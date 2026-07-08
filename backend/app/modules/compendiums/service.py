import re

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compendium_section import CompendiumSection, SectionStatus
from app.models.extraction import Extraction, ExtractionStatus
from app.models.project import Project, ProjectStatus
from app.models.source_document import SourceDocument
from app.modules.prompts.section_builder import DOSIFICATION_MAP, SECTION_CONFIGS

MARCADOR_CONTINUACION = re.compile(r"\[CONTINÚA.*?\]", re.IGNORECASE | re.DOTALL)
HIDE_ALL_ARTIFACT = re.compile(r"strongHIDE\s+ALL|HIDE\s+ALL", re.IGNORECASE)


async def merge_extractions(
    db: AsyncSession,
    project: Project,
) -> Project:
    if project.status not in (
        ProjectStatus.DRAFT,
        ProjectStatus.EXTRACTING,
        ProjectStatus.REVIEW,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"El proyecto no permite fusionar extracciones "
                f"(estado actual: {project.status})"
            ),
        )

    result = await db.execute(
        select(Extraction)
        .join(SourceDocument, SourceDocument.id == Extraction.source_document_id)
        .where(
            SourceDocument.project_id == project.id,
            Extraction.status == ExtractionStatus.COMPLETED,
        )
        .order_by(SourceDocument.created_at)
    )
    extractions = list(result.scalars().all())

    if not extractions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No hay extracciones completadas para fusionar",
        )

    parts = []
    for ext in extractions:
        text = ext.content or ""
        text = MARCADOR_CONTINUACION.sub("", text)
        text = HIDE_ALL_ARTIFACT.sub("", text)
        parts.append(text.strip())

    merged = "\n\n".join(parts)
    project.merged_content = merged
    await db.commit()
    await db.refresh(project)
    return project


async def generate_sections(
    db: AsyncSession,
    project: Project,
    arq_pool=None,
) -> dict:
    if project.status not in (ProjectStatus.DRAFT, ProjectStatus.REVIEW):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"El proyecto no permite generar compendio "
                f"(estado actual: {project.status})"
            ),
        )

    if not project.merged_content or not project.merged_content.strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El proyecto no tiene contenido fusionado. Ejecuta el merge primero.",
        )

    existing_result = await db.execute(
        select(CompendiumSection).where(CompendiumSection.project_id == project.id)
    )
    existing_sections = {s.section_number: s for s in existing_result.scalars().all()}

    created = 0
    for section_number in range(1, 12):
        config = SECTION_CONFIGS[section_number]
        if section_number in existing_sections:
            section = existing_sections[section_number]
            section.status = SectionStatus.PENDING
            section.content = ""
            section.error_message = None
        else:
            section = CompendiumSection(
                project_id=project.id,
                section_number=section_number,
                section_name=config.section_name,
                dosification=DOSIFICATION_MAP[config.dosification_level],
                status=SectionStatus.PENDING,
            )
            db.add(section)
            created += 1

    if ProjectStatus.is_valid_transition(project.status, ProjectStatus.GENERATING):
        project.set_status(ProjectStatus.GENERATING)

    await db.commit()

    if arq_pool is not None:
        for section_number in range(1, 12):
            await arq_pool.enqueue_job(
                "generate_section",
                project_id=str(project.id),
                section_number=section_number,
                _job_id=f"generate_{project.id}_{section_number}",
            )

    return {
        "project_id": str(project.id),
        "sections_created": created,
        "project_status": project.status,
    }


async def get_sections_for_project(
    db: AsyncSession,
    project_id: str,
) -> list[CompendiumSection]:
    result = await db.execute(
        select(CompendiumSection)
        .where(CompendiumSection.project_id == project_id)
        .order_by(CompendiumSection.section_number)
    )
    return list(result.scalars().all())


async def get_section(
    db: AsyncSession,
    section_id: str,
) -> CompendiumSection:
    result = await db.execute(
        select(CompendiumSection).where(CompendiumSection.id == section_id)
    )
    section = result.scalar_one_or_none()
    if section is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sección no encontrada",
        )
    return section


async def update_section(
    db: AsyncSession,
    section: CompendiumSection,
    content: str,
) -> CompendiumSection:
    section.content = content
    if section.status == SectionStatus.FAILED:
        section.status = SectionStatus.COMPLETED
    await db.commit()
    await db.refresh(section)
    return section


async def regenerate_section(
    db: AsyncSession,
    section: CompendiumSection,
    arq_pool=None,
) -> CompendiumSection:
    if section.status not in (
        SectionStatus.COMPLETED,
        SectionStatus.FAILED,
        SectionStatus.APPROVED,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Solo se pueden regenerar secciones completadas o fallidas "
                f"(estado actual: {section.status})"
            ),
        )

    section.status = SectionStatus.PENDING
    section.content = ""
    section.error_message = None
    await db.commit()
    await db.refresh(section)

    if arq_pool is not None:
        await arq_pool.enqueue_job(
            "generate_section",
            project_id=str(section.project_id),
            section_number=section.section_number,
            _job_id=f"generate_{section.project_id}_{section.section_number}",
        )

    return section
