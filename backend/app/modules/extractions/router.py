from uuid import UUID

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_arq_pool
from app.models.extraction import Extraction
from app.models.project import Project
from app.models.source_document import SourceDocument, SourceDocumentStatus
from app.models.user import User
from app.modules.auth.dependencies import get_current_user
from app.modules.extractions.dependencies import (
    get_document_for_extract,
    get_extraction_or_404,
)
from app.modules.extractions.schemas import (
    ExtractAllResponse,
    ExtractRequest,
    ExtractionResponse,
    ExtractionStatusResponse,
    RetryResponse,
)
from app.modules.extractions.service import (
    extract_all_for_project,
    get_extraction,
    retry_extraction,
    start_extraction,
)
from app.modules.projects.dependencies import get_project_or_404

router = APIRouter(tags=["Extractions"])


@router.post(
    "/documents/{document_id}/extract",
    response_model=ExtractionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def extract(
    body: ExtractRequest | None = None,
    document: SourceDocument = Depends(get_document_for_extract),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis | None = Depends(get_arq_pool),
) -> Extraction:
    extraction = await start_extraction(db, document)
    if arq_pool is not None:
        job_kwargs: dict = {
            "document_id": str(document.id),
            "_job_id": f"extract_{document.id}",
        }
        if body and body.extraction_model:
            job_kwargs["model"] = body.extraction_model
        await arq_pool.enqueue_job("extract_document", **job_kwargs)
    return extraction


@router.get(
    "/extractions/{extraction_id}",
    response_model=ExtractionResponse,
)
async def get_one(
    extraction: Extraction = Depends(get_extraction_or_404),
) -> Extraction:
    return extraction


@router.get(
    "/extractions/{extraction_id}/status",
    response_model=ExtractionStatusResponse,
)
async def get_status(
    extraction: Extraction = Depends(get_extraction_or_404),
) -> Extraction:
    return extraction


@router.post(
    "/extractions/{extraction_id}/retry",
    response_model=RetryResponse,
)
async def retry(
    body: ExtractRequest | None = None,
    extraction: Extraction = Depends(get_extraction_or_404),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis | None = Depends(get_arq_pool),
) -> dict:
    result = await retry_extraction(db, extraction)
    if arq_pool is not None:
        job_kwargs: dict = {
            "document_id": str(extraction.source_document_id),
            "_job_id": f"extract_{extraction.source_document_id}",
        }
        if body and body.extraction_model:
            job_kwargs["model"] = body.extraction_model
        await arq_pool.enqueue_job("extract_document", **job_kwargs)
    return {
        "id": result.id,
        "status": result.status,
        "message": "Extracción en cola para reintento",
    }


@router.post(
    "/projects/{project_id}/extract-all",
    response_model=ExtractAllResponse,
)
async def extract_all(
    body: ExtractRequest | None = None,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis | None = Depends(get_arq_pool),
) -> dict:
    data = await extract_all_for_project(db, project)

    if data["enqueued"] > 0 and arq_pool is not None:
        result = await db.execute(
            select(SourceDocument).where(
                SourceDocument.project_id == project.id,
                SourceDocument.status == SourceDocumentStatus.EXTRACTING,
            )
        )
        extractable_docs = list(result.scalars().all())
        for doc in extractable_docs:
            job_kwargs: dict = {
                "document_id": str(doc.id),
                "_job_id": f"extract_{doc.id}",
            }
            if body and body.extraction_model:
                job_kwargs["model"] = body.extraction_model
            await arq_pool.enqueue_job("extract_document", **job_kwargs)

    return data
