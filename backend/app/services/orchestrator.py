"""
PipelineOrchestrator — coordina la generación de un compendio completo
manteniendo continuidad real de contexto entre secciones (hilo
acumulado derivado del estado de la BD), con motor resuelto por
sección, soporte de co-generación 4-5 (Tarea 5) y verificación de
mapa de ecos aprobado (Tarea 3).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.compendium_section import CompendiumSection, SectionStatus
from app.models.project import Project, ProjectStatus
from app.modules.ai_gateway.conversation import Conversation
from app.modules.ai_gateway.errors import format_ai_error
from app.modules.ai_gateway.interfaces import AIGatewayClient
from app.modules.ai_gateway.models import DEFAULT_GENERATION_MODEL
from app.modules.ai_gateway.openrouter_client import OpenRouterClient
from app.modules.compendiums.service import sanitize_section_content
from app.modules.prompts.ecos_service import (
    get_active_ecos_map,
    get_ecos_for_section,
    pathology_key_for,
)
from app.modules.prompts.section_builder import (
    DOSIFICATION_MAP,
    MAX_TOKENS_BY_DOSIFICATION,
    SECTION_CONFIGS,
    build_section_instruction,
    build_thread_init_message,
)
from app.modules.prompts.service import get_active_prompt

# ── Motor por defecto por sección (placeholder Tarea 4) ──────────────
# Mientras Tarea 4 no decida el mapa final, ambos motores resuelven al
# default; este mapa se inyecta en MOTOR_MODEL_MAP global que los tests
# sobreescriben.
DEFAULT_MOTOR_MODEL_MAP: dict[str, str] = {
    "gemini": DEFAULT_GENERATION_MODEL,
    "claude": "anthropic/claude-sonnet-5",
}

# Pares de co-generación (R-9): la sección 5 hereda el motor de la 4.
COGENERATION_PAIRS: dict[int, int] = {5: 4}


@dataclass
class OrchestratorResult:
    project_id: str
    completed: int
    failed: list[int]
    status: str


def _resolve_motor_for_section(
    section_number: int,
    motor_model_map: dict[str, str],
    prior_pair_motor: str | None = None,
) -> str:
    if section_number in COGENERATION_PAIRS and prior_pair_motor is not None:
        return prior_pair_motor
    return SECTION_CONFIGS[section_number].motor


def _resolve_model_id(
    motor: str,
    motor_model_map: dict[str, str],
) -> str:
    return motor_model_map.get(motor, DEFAULT_GENERATION_MODEL)


def _build_extra_params(motor: str, section_number: int, model_id: str) -> dict:
    """
    Tarea 1: extended thinking REAL para Claude en secciones 🔴.
    OpenRouter espera `reasoning: {enabled: True}` (NO `thinking`
    como decía docs/09 — el formato real es `reasoning`).
    Solo se activa si el modelo resuelto es realmente un modelo Claude.
    """
    config = SECTION_CONFIGS[section_number]
    if "claude" not in (model_id or "").lower():
        return {}
    if motor == "claude" and "🔴" in config.dosification_level:
        return {"reasoning": {"enabled": True, "max_tokens": 16000}}
    return {}


def _infer_motor_from_model(model_id: str) -> str:
    mid = (model_id or "").lower()
    if "claude" in mid:
        return "claude"
    return "gemini"


def _replay_conversation(
    project: Project,
    sections_by_number: dict[int, CompendiumSection],
    section_number: int,
    system_prompt: str,
    patch_gemini: str | None,
    source_filename: str,
    eco_map: object | None = None,
) -> Conversation:
    use_gemini_patch = (
        SECTION_CONFIGS[1].motor == "gemini" and patch_gemini is not None
    )
    conv = Conversation()
    init_msg = build_thread_init_message(
        system_prompt=system_prompt,
        pathology_name=project.name,
        source_filename=source_filename,
        merged_content=project.merged_content or "",
        patch_gemini=patch_gemini if use_gemini_patch else None,
    )
    conv.add_user(init_msg.content)

    for n in sorted(sections_by_number.keys()):
        if n >= section_number:
            break
        prior = sections_by_number[n]
        prior_ecos = get_ecos_for_section(eco_map, n)
        instruction = build_section_instruction(
            section_number=n,
            pathology_name=project.name,
            source_filename=source_filename,
            is_last=(n == 11),
            ecos=prior_ecos,
        )
        conv.add_user(instruction)
        conv.add_assistant(prior.content or "")

    return conv


async def _load_sections_map(
    db: AsyncSession, project_id: str
) -> dict[int, CompendiumSection]:
    result = await db.execute(
        select(CompendiumSection).where(
            CompendiumSection.project_id == project_id
        )
    )
    return {s.section_number: s for s in result.scalars().all()}


class PipelineOrchestrator:
    def __init__(
        self,
        ai_client: AIGatewayClient | None = None,
        motor_model_map: dict[str, str] | None = None,
    ):
        self.ai = ai_client or OpenRouterClient()
        self.motor_model_map = (
            motor_model_map
            if motor_model_map is not None
            else dict(DEFAULT_MOTOR_MODEL_MAP)
        )

    async def generate_all_sections(
        self,
        project_id: str,
        motor_model_map: dict[str, str] | None = None,
        eco_map_lookup=None,
        eco_map=None,
        _db: AsyncSession | None = None,
    ) -> OrchestratorResult:
        motor_map = (
            dict(motor_model_map)
            if motor_model_map is not None
            else dict(self.motor_model_map)
        )

        if _db is not None:
            return await self._run_generate(
                project_id=project_id,
                motor_map=motor_map,
                eco_map_lookup=eco_map_lookup,
                eco_map=eco_map,
                db=_db,
            )

        async with async_session() as db:
            return await self._run_generate(
                project_id=project_id,
                motor_map=motor_map,
                eco_map_lookup=eco_map_lookup,
                eco_map=eco_map,
                db=db,
            )

    async def _run_generate(
        self,
        project_id: str,
        motor_map: dict[str, str],
        eco_map_lookup,
        eco_map,
        db: AsyncSession,
    ) -> OrchestratorResult:
        project = (
            await db.execute(
                select(Project).where(Project.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            return OrchestratorResult(
                project_id=project_id,
                completed=0,
                failed=list(range(1, 12)),
                status="error:project_not_found",
            )

        if project.status not in (
            ProjectStatus.DRAFT,
            ProjectStatus.REVIEW,
            ProjectStatus.GENERATING,
        ):
            return OrchestratorResult(
                project_id=project_id,
                completed=0,
                failed=[],
                status=f"error:invalid_state:{project.status}",
            )

        # DRAFT/REVIEW → GENERATING (transición válida en FSM).
        if (
            project.status
            in (ProjectStatus.DRAFT, ProjectStatus.REVIEW)
            and ProjectStatus.is_valid_transition(
                project.status, ProjectStatus.GENERATING
            )
        ):
            project.set_status(ProjectStatus.GENERATING)
            await db.commit()

        source_filename = (
            ", ".join(doc.filename for doc in project.documents)
            if project.documents
            else "N/A"
        )

        system_prompt_rec = await get_active_prompt(
            db, "system_prompt_sam_v9"
        )
        patch_gemini = None
        first_motor = SECTION_CONFIGS[1].motor
        if first_motor == "gemini":
            patch_rec = await get_active_prompt(
                db, "patch_gemini_density"
            )
            patch_gemini = patch_rec.content

        # Tarea 3: mapa de ecos aprobado o bloquear.
        pathology_key = pathology_key_for(project.name)
        if eco_map is not None:
            pass
        elif eco_map_lookup is not None:
            eco_lookup_result = await eco_map_lookup(db, project)
            if not eco_lookup_result.get("ok"):
                if ProjectStatus.is_valid_transition(
                    project.status, ProjectStatus.DRAFT
                ):
                    project.set_status(ProjectStatus.DRAFT)
                await db.commit()
                return OrchestratorResult(
                    project_id=project_id,
                    completed=0,
                    failed=[],
                    status=(
                        f"error:eco_map_block:"
                        f"{eco_lookup_result.get('reason', '')}"
                    ),
                )
        else:
            eco_map = await get_active_ecos_map(db, pathology_key)
            if eco_map is None:
                if ProjectStatus.is_valid_transition(
                    project.status, ProjectStatus.DRAFT
                ):
                    project.set_status(ProjectStatus.DRAFT)
                await db.commit()
                return OrchestratorResult(
                    project_id=project_id,
                    completed=0,
                    failed=[],
                    status=(
                        f"error:eco_map_not_approved:{pathology_key}"
                    ),
                )

        completed = 0
        failed: list[int] = []
        sections_by_number: dict[int, CompendiumSection] = {}

        for section_number in range(1, 12):
            sections_by_number = await _load_sections_map(
                db, project_id
            )
            section = sections_by_number.get(section_number)
            if section is None:
                failed.append(section_number)
                continue

            if (
                section.status == SectionStatus.COMPLETED
                and section.content
            ):
                completed += 1
                continue

            try:
                section.status = SectionStatus.PROCESSING
                await db.commit()

                anchor_motor = None
                if section_number in COGENERATION_PAIRS:
                    anchor = sections_by_number.get(
                        COGENERATION_PAIRS[section_number]
                    )
                    if anchor and anchor.model_used:
                        anchor_motor = _infer_motor_from_model(
                            anchor.model_used
                        )

                motor = _resolve_motor_for_section(
                    section_number,
                    motor_map,
                    prior_pair_motor=anchor_motor,
                )
                model_id = _resolve_model_id(motor, motor_map)
                extra_params = _build_extra_params(
                    motor, section_number, model_id
                )

                section_ecos = get_ecos_for_section(
                    eco_map, section_number
                )

                conv = _replay_conversation(
                    project=project,
                    sections_by_number=sections_by_number,
                    section_number=section_number,
                    system_prompt=system_prompt_rec.content,
                    patch_gemini=patch_gemini,
                    source_filename=source_filename,
                    eco_map=eco_map,
                )

                instruction = build_section_instruction(
                    section_number=section_number,
                    pathology_name=project.name,
                    source_filename=source_filename,
                    is_last=(section_number == 11),
                    ecos=section_ecos,
                )

                max_tokens = MAX_TOKENS_BY_DOSIFICATION.get(
                    DOSIFICATION_MAP.get(
                        SECTION_CONFIGS[
                            section_number
                        ].dosification_level,
                        "STANDARD",
                    ),
                    8192,
                )

                ai_result = await self.ai.generate_in_conversation(
                    conversation=conv,
                    user_message=instruction,
                    model=model_id,
                    temperature=0.1,
                    max_tokens=max_tokens,
                    max_continuations=10,
                    **extra_params,
                )

                from app.modules.ai_gateway.conversation import (
                    Conversation as _Conv,
                )
                if _Conv.is_truncated(ai_result.finish_reason):
                    from app.modules.ai_gateway.openrouter_client import (
                        ContinuationExhaustedError,
                    )
                    raise ContinuationExhaustedError(
                        f"section {section_number} truncada tras "
                        f"agotar continuaciones "
                        f"(finish_reason={ai_result.finish_reason})"
                    )

                if ai_result.finish_reason == "content_filter":
                    raise ValueError(
                        f"Sección {section_number} bloqueada por filtro "
                        f"de contenido del proveedor (content_filter)."
                    )

                cleaned = sanitize_section_content(ai_result.content)
                if not cleaned:
                    raise ValueError(
                        f"Sección {section_number} devolvió contenido vacío."
                    )

                section.content = cleaned
                section.model_used = ai_result.model
                section.input_tokens = ai_result.input_tokens
                section.output_tokens = ai_result.output_tokens
                section.cost_usd = ai_result.cost_usd
                section.prompt_version = str(
                    system_prompt_rec.version
                )
                section.ecos_map_version = (
                    f"v{eco_map.version}" if eco_map else None
                )
                section.status = SectionStatus.COMPLETED
                section.is_stale = False
                await db.commit()
                completed += 1

            except Exception as exc:
                section.status = SectionStatus.FAILED
                section.error_message = format_ai_error(exc)
                await db.commit()
                failed.append(section_number)
                break

        # Estado final
        final_status = project.status
        if (
            project.status == ProjectStatus.GENERATING
            and ProjectStatus.is_valid_transition(
                project.status, ProjectStatus.REVIEW
            )
        ):
            project.set_status(ProjectStatus.REVIEW)
            await db.commit()
            final_status = ProjectStatus.REVIEW

        return OrchestratorResult(
            project_id=project_id,
            completed=completed,
            failed=failed,
            status=final_status,
        )

    async def regenerate_single_section(
        self,
        project_id: str,
        section_number: int,
        motor_model_map: dict[str, str] | None = None,
        eco_map_lookup=None,
    ) -> OrchestratorResult:
        motor_map = (
            dict(motor_model_map)
            if motor_model_map is not None
            else dict(self.motor_model_map)
        )

        # Cascada R-9: regenerar 4 implica regenerar 5.
        target_sections = [section_number]
        if section_number in (4, 5):
            other = 5 if section_number == 4 else 4
            target_sections = sorted({section_number, other})

        async with async_session() as db:
            project = (
                await db.execute(
                    select(Project).where(Project.id == project_id)
                )
            ).scalar_one_or_none()
            if project is None:
                return OrchestratorResult(
                    project_id=project_id,
                    completed=0,
                    failed=target_sections,
                    status="error:project_not_found",
                )

            for n in target_sections:
                sections_map = await _load_sections_map(db, project_id)
                section = sections_map.get(n)
                if section is None:
                    continue
                section.status = SectionStatus.PENDING
                section.content = ""
                section.error_message = None

            # Mark downstream sections as stale (they were generated
            # from the old content of the section being regenerated).
            max_target = max(target_sections)
            for s in sections_map.values():
                if s.section_number > max_target and s.status == SectionStatus.COMPLETED:
                    s.is_stale = True

            await db.commit()

        return await self.generate_all_sections(
            project_id=project_id,
            motor_model_map=motor_map,
            eco_map_lookup=eco_map_lookup,
        )
