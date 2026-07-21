from contextlib import asynccontextmanager
from tempfile import NamedTemporaryFile

import pymupdf4llm
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.extraction import Extraction, ExtractionStatus
from app.models.project import Project, ProjectStatus
from app.models.source_document import SourceDocument, SourceDocumentStatus
from app.modules.ai_gateway.errors import format_ai_error
from app.modules.ai_gateway.models import DEFAULT_EXTRACTION_MODEL
from app.modules.ai_gateway.openrouter_client import OpenRouterClient
from app.modules.audit.service import run_audit_for_extraction
from app.modules.prompts.service import get_active_prompt
from app.services.storage import get_storage_backend

log = structlog.get_logger()

DOC_TYPE_PROMPT_MAP = {
    "bmj": "extraction_v3_bmj",
    "guideline": "extraction_v5_guideline",
    "article": "extraction_articles",
}


@asynccontextmanager
async def _get_session(db: AsyncSession | None):
    if db is not None:
        yield db
    else:
        async with async_session() as new_db:
            yield new_db


async def _check_project_extractions_done(
    db: AsyncSession, project_id: str
) -> None:
    docs_result = await db.execute(
        select(SourceDocument).where(SourceDocument.project_id == project_id)
    )
    all_docs = list(docs_result.scalars().all())

    all_done = all(
        doc.status in (SourceDocumentStatus.EXTRACTED, SourceDocumentStatus.ERROR)
        for doc in all_docs
    )

    if not all_done:
        return

    project_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        return

    if project.status == ProjectStatus.EXTRACTING:
        project.set_status(ProjectStatus.DRAFT)
        await db.commit()
        log.info(
            "project_transitioned_to_draft",
            project_id=str(project.id),
            total_documents=len(all_docs),
        )


async def extract_document(
    ctx: dict,
    document_id: str,
    model: str | None = None,
    _db: AsyncSession | None = None,
) -> dict:
    async with _get_session(_db) as db:
        result = await db.execute(
            select(Extraction).where(
                Extraction.source_document_id == document_id
            )
        )
        extraction = result.scalar_one_or_none()
        if extraction is None:
            return {"status": "error", "detail": "Extraction not found"}

        doc_result = await db.execute(
            select(SourceDocument).where(SourceDocument.id == document_id)
        )
        document = doc_result.scalar_one_or_none()
        if document is None:
            return {"status": "error", "detail": "Document not found"}

        extraction.status = ExtractionStatus.PROCESSING
        await db.commit()

        try:
            storage = get_storage_backend()
            pdf_bytes = await storage.read_bytes(document.file_path)

            with NamedTemporaryFile(
                suffix=".pdf", dir="/tmp", delete=True
            ) as tmp:
                tmp.write(pdf_bytes)
                tmp.flush()
                pdf_text = pymupdf4llm.to_markdown(tmp.name)

            prompt_name = DOC_TYPE_PROMPT_MAP.get(
                document.document_type, "extraction_articles"
            )
            extraction_prompt = await get_active_prompt(db, prompt_name)

            full_prompt = (
                f"{extraction_prompt.content}\n\n"
                f"{'=' * 70}\n"
                f"DOCUMENTO FUENTE ({document.filename}):\n"
                f"{'=' * 70}\n\n"
                f"{pdf_text}"
            )

            model_id = model or DEFAULT_EXTRACTION_MODEL
            ai = OpenRouterClient()
            ai_result = await ai.generate_with_continuations(
                prompt=full_prompt,
                model=model_id,
                temperature=0.1,
            )

            extraction.content = ai_result.content
            extraction.model_used = ai_result.model
            extraction.input_tokens = ai_result.input_tokens
            extraction.output_tokens = ai_result.output_tokens
            extraction.cost_usd = ai_result.cost_usd
            extraction.status = ExtractionStatus.COMPLETED
            document.set_status(SourceDocumentStatus.EXTRACTED)
            await db.commit()

            log.info(
                "extraction_completed",
                extraction_id=str(extraction.id),
                document_id=str(document.id),
                model=ai_result.model,
                input_tokens=ai_result.input_tokens,
                output_tokens=ai_result.output_tokens,
                cost_usd=float(ai_result.cost_usd),
            )

            await _check_project_extractions_done(db, document.project_id)

            arq_pool = ctx.get("arq_pool")
            if arq_pool is not None:
                await arq_pool.enqueue_job(
                    "audit_extraction",
                    extraction_id=str(extraction.id),
                    _job_id=f"audit_{extraction.id}",
                )

            return {"status": "completed"}

        except Exception as exc:
            extraction.status = ExtractionStatus.FAILED
            extraction.error_message = format_ai_error(exc)
            document.set_status(SourceDocumentStatus.ERROR)
            await db.commit()

            log.error(
                "extraction_failed",
                extraction_id=str(extraction.id),
                document_id=str(document.id),
                error=str(exc),
            )

            await _check_project_extractions_done(db, document.project_id)

            return {"status": "failed", "error": format_ai_error(exc)}


async def audit_extraction(
    ctx: dict,
    extraction_id: str,
    _db: AsyncSession | None = None,
) -> dict:
    """
    Tarea 2: auditoría v1 contra checklist curado en prompt_templates.
    Compara el contenido de la extracción contra los hechos esperados
    del tipo de documento y persiste el reporte (con la lista de
    faltantes) en `extraction.audit_content`.

    Nunca falla la extracción: si el checklist no está disponible
    o la extracción no existe, se loguea y se retorna error suave.
    """
    async with _get_session(_db) as db:
        result = await db.execute(
            select(Extraction).where(Extraction.id == extraction_id)
        )
        extraction = result.scalar_one_or_none()
        if extraction is None:
            log.warning("audit_extraction.not_found", extraction_id=extraction_id)
            return {"status": "skipped", "reason": "extraction_not_found"}

        doc_result = await db.execute(
            select(SourceDocument).where(
                SourceDocument.id == extraction.source_document_id
            )
        )
        document = doc_result.scalar_one_or_none()
        if document is None:
            log.warning(
                "audit_extraction.document_not_found",
                extraction_id=extraction_id,
            )
            return {"status": "skipped", "reason": "document_not_found"}

        try:
            report = await run_audit_for_extraction(db, extraction, document)
            log.info(
                "audit_extraction_completed",
                extraction_id=str(extraction.id),
                document_id=str(document.id),
                checklist=report.checklist_name,
                missing_count=report.missing_count,
                present_count=report.present_count,
                total_facts=report.total_facts,
            )
            if report.missing_count > 0:
                log.warning(
                    "audit_extraction_missing_facts",
                    extraction_id=str(extraction.id),
                    missing_ids=[f.id for f in report.missing],
                )
            return {
                "status": "completed",
                "missing_count": report.missing_count,
                "present_count": report.present_count,
                "total_facts": report.total_facts,
            }
        except Exception as exc:
            log.error(
                "audit_extraction_failed",
                extraction_id=extraction_id,
                error=str(exc),
            )
            return {"status": "failed", "error": format_ai_error(exc)}
