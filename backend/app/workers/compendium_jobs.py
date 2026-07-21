"""
Jobs ARQ para orquestación del compendio completo.

- `generate_compendium`: dispara el PipelineOrchestrator para
  generar las 11 secciones en orden, con continuidad real de
  contexto entre secciones.
- `regenerate_section_job`: regenera una sección individual
  (cascada R-9 si es la 4 o la 5).
"""

from __future__ import annotations

from arq.connections import ArqRedis

from app.services.orchestrator import PipelineOrchestrator


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
