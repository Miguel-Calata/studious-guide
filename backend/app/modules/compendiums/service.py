import logging
import re

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compendium_section import CompendiumSection, SectionStatus
from app.models.extraction import Extraction, ExtractionStatus
from app.models.project import Project, ProjectStatus
from app.models.source_document import SourceDocument
from app.modules.prompts.ecos_service import (
    get_active_ecos_map,
    get_pending_draft,
    pathology_key_for,
)
from app.modules.prompts.section_builder import DOSIFICATION_MAP, SECTION_CONFIGS

log = logging.getLogger(__name__)

MARCADOR_CONTINUACION = re.compile(r"\[CONTINÚA.*?\]", re.IGNORECASE | re.DOTALL)
FIN_PARTE_MARKER = re.compile(r"\[Fin de la Parte[^\]]*\]", re.IGNORECASE | re.DOTALL)
HIDE_ALL_ARTIFACT = re.compile(r"strongHIDE\s+ALL|HIDE\s+ALL", re.IGNORECASE)


def sanitize_section_content(content: str) -> str:
    if not content:
        return content
    text = MARCADOR_CONTINUACION.sub("", content)
    text = FIN_PARTE_MARKER.sub("", text)
    text = HIDE_ALL_ARTIFACT.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def merge_extractions(
    db: AsyncSession,
    project: Project,
    arq_pool=None,
) -> dict:
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

    # Collect warnings for failed/pending documents
    warnings: list[str] = []
    all_docs_result = await db.execute(
        select(SourceDocument).where(SourceDocument.project_id == project.id)
    )
    all_docs = list(all_docs_result.scalars().all())
    completed_doc_ids = {ext.source_document_id for ext in extractions}
    for doc in all_docs:
        if doc.id not in completed_doc_ids:
            warnings.append(
                f"Documento '{doc.filename}' no tiene extracción "
                f"completada y fue excluido del contenido fusionado."
            )

    parts = []
    for ext in extractions:
        text = sanitize_section_content(ext.content or "")
        parts.append(text.strip())

    merged = "\n\n".join(parts)
    project.merged_content = merged
    await db.commit()
    await db.refresh(project)

    # Auto-propose ecos map draft en background si no hay mapa
    # aprobado ni borrador pendiente para esta patología.
    ecos_map_enqueued = False
    if arq_pool is not None:
        pathology_key = pathology_key_for(project.name)
        active_map = await get_active_ecos_map(db, pathology_key)
        pending = await get_pending_draft(db, pathology_key)
        if active_map is None and pending is None:
            try:
                await arq_pool.enqueue_job(
                    "propose_ecos_map_job",
                    project_id=str(project.id),
                    _job_id=f"propose_ecos_map_{pathology_key}",
                )
                ecos_map_enqueued = True
                log.info(
                    "ecos_map_auto_propose_enqueued",
                    project_id=str(project.id),
                    pathology_key=pathology_key,
                )
            except Exception:
                log.warning(
                    "ecos_map_auto_propose_enqueue_failed",
                    project_id=str(project.id),
                    exc_info=True,
                )

    return {
        "project": project,
        "warnings": warnings,
        "ecos_map_enqueued": ecos_map_enqueued,
    }


async def generate_sections(
    db: AsyncSession,
    project: Project,
    arq_pool=None,
    model_overrides: dict | None = None,
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

    # Tarea 3: bloquear 409 si no hay ecos map aprobado para esta
    # patología. Con auto-propose activado, el borrador se genera
    # tras merge; si aún no está aprobado, el usuario debe
    # revisarlo y aprobarlo antes de poder generar.
    pathology_key = pathology_key_for(project.name)
    eco_map = await get_active_ecos_map(db, pathology_key)
    if eco_map is None:
        # Verificar si hay un borrador pendiente de revisión
        pending = await get_pending_draft(db, pathology_key)
        if pending is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Hay un borrador del ecos map pendiente de "
                    f"revisión y aprobación para '{project.name}' "
                    f"(id='{pending.id}', v{pending.version}). "
                    f"Revísalo y apruébalo con "
                    f"POST /api/v1/ecos-maps/{pending.id}/approve "
                    f"antes de generar."
                ),
            )
        # Sin mapa ni borrador: fallback — encolar auto-propose
        if arq_pool is not None:
            try:
                await arq_pool.enqueue_job(
                    "propose_ecos_map_job",
                    project_id=str(project.id),
                    _job_id=f"propose_ecos_map_{pathology_key}",
                )
            except Exception:
                log.warning(
                    "ecos_map_fallback_propose_failed",
                    project_id=str(project.id),
                    exc_info=True,
                )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No existe ecos_map aprobado para la patología "
                f"'{project.name}' (key='{pathology_key}'). "
                + (
                    "Se ha generado un borrador en segundo plano; "
                    "revísalo y apruébalo cuando esté listo."
                    if arq_pool is not None
                    else "Genera un borrador con "
                    f"POST /api/v1/pathologies/{pathology_key}/"
                    f"ecos-map:propose y apruébalo antes de generar."
                )
            ),
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
        # Tarea 1: el hilo acumulado de conversación obliga a
        # generación SECUENCIAL 1 → 11. Encolamos un único job
        # "generate_compendium" que el PipelineOrchestrator ejecuta
        # en orden. El modelo por sección se resuelve internamente.
        job_kwargs: dict = {
            "project_id": str(project.id),
            "_job_id": f"generate_compendium_{project.id}",
        }
        if model_overrides:
            job_kwargs["motor_model_map"] = model_overrides
        await arq_pool.enqueue_job("generate_compendium", **job_kwargs)

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
    model_overrides: dict | None = None,
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
        # Tarea 1 + Tarea 5: regenerar la 4 implica regenerar la 5
        # (par R-9, mismo motor). El orchestrator gestiona la cascada.
        job_kwargs: dict = {
            "project_id": str(section.project_id),
            "section_number": section.section_number,
            "_job_id": f"regenerate_{section.project_id}_{section.section_number}",
        }
        if model_overrides:
            job_kwargs["motor_model_map"] = model_overrides
        await arq_pool.enqueue_job("regenerate_section_job", **job_kwargs)

    return section
