"""
Jobs ARQ para orquestación del compendio completo.

- `generate_compendium`: dispara el PipelineOrchestrator para
  generar las 11 secciones en orden, con continuidad real de
  contexto entre secciones.
- `regenerate_section_job`: regenera una sección individual
  (cascada R-9 si es la 4 o la 5).
- `propose_ecos_map_job`: genera un borrador de ecos map
  grounded en el merged_content del proyecto (auto-propose).
"""

from __future__ import annotations

import structlog
from arq.connections import ArqRedis
from sqlalchemy import select

from app.database import async_session
from app.models.project import Project
from app.modules.ai_gateway.openrouter_client import OpenRouterClient
from app.modules.prompts.ecos_service import (
    get_active_ecos_map,
    get_pending_draft,
    pathology_key_for,
    propose_ecos_map,
)
from app.services.orchestrator import PipelineOrchestrator

log = structlog.get_logger()


async def _get_arq_pool(ctx: dict) -> ArqRedis | None:
    return ctx.get("arq_pool") if ctx else None


async def generate_compendium(
    ctx: dict,
    project_id: str,
    motor_model_map: dict | None = None,
) -> dict:
    orchestrator = PipelineOrchestrator(
        motor_model_map=motor_model_map or None
    )
    result = await orchestrator.generate_all_sections(
        project_id=project_id,
        motor_model_map=motor_model_map,
    )
    return {
        "status": "completed" if not result.failed else "partial",
        "project_id": result.project_id,
        "completed": result.completed,
        "failed": result.failed,
        "project_status": result.status,
    }


async def regenerate_section_job(
    ctx: dict,
    project_id: str,
    section_number: int,
    motor_model_map: dict | None = None,
) -> dict:
    orchestrator = PipelineOrchestrator(
        motor_model_map=motor_model_map or None
    )
    result = await orchestrator.regenerate_single_section(
        project_id=project_id,
        section_number=section_number,
        motor_model_map=motor_model_map,
    )
    return {
        "status": "completed" if not result.failed else "partial",
        "project_id": result.project_id,
        "completed": result.completed,
        "failed": result.failed,
        "section_number": section_number,
    }


async def propose_ecos_map_job(
    ctx: dict,
    project_id: str,
    model: str | None = None,
) -> dict:
    """
    Auto-propose de ecos map grounded en merged_content.
    Idempotente: no hace nada si ya hay mapa aprobado o borrador
    pendiente para la patología del proyecto.
    """
    async with async_session() as db:
        project = (
            await db.execute(
                select(Project).where(Project.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            log.warning(
                "propose_ecos_map_job_project_not_found",
                project_id=project_id,
            )
            return {"status": "skipped", "reason": "project_not_found"}

        pathology_key = pathology_key_for(project.name)

        # Idempotencia: saltar si ya hay mapa aprobado
        active = await get_active_ecos_map(db, pathology_key)
        if active is not None:
            log.info(
                "propose_ecos_map_job_already_approved",
                project_id=project_id,
                pathology_key=pathology_key,
            )
            return {"status": "skipped", "reason": "already_approved"}

        # Idempotencia: saltar si ya hay borrador pendiente
        pending = await get_pending_draft(db, pathology_key)
        if pending is not None:
            log.info(
                "propose_ecos_map_job_draft_exists",
                project_id=project_id,
                pathology_key=pathology_key,
                draft_id=pending.id,
            )
            return {"status": "skipped", "reason": "draft_exists"}

        try:
            ai = OpenRouterClient()
            eco_map = await propose_ecos_map(
                db,
                ai,
                project.name,
                source_content=project.merged_content,
                model=model,
            )
            log.info(
                "propose_ecos_map_job_completed",
                project_id=project_id,
                pathology_key=pathology_key,
                ecos_map_id=eco_map.id,
                version=eco_map.version,
            )
            return {
                "status": "completed",
                "ecos_map_id": eco_map.id,
                "version": eco_map.version,
                "pathology_key": pathology_key,
            }
        except Exception:
            log.error(
                "propose_ecos_map_job_failed",
                project_id=project_id,
                pathology_key=pathology_key,
                exc_info=True,
            )
            return {"status": "failed", "reason": "llm_error"}
