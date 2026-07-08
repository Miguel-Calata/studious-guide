import structlog
from contextlib import asynccontextmanager

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.compendium_section import CompendiumSection, SectionStatus
from app.models.project import Project, ProjectStatus
from app.modules.ai_gateway.openrouter_client import OpenRouterClient
from app.modules.prompts.section_builder import (
    DOSIFICATION_MAP,
    SECTION_CONFIGS,
    build_section_prompt,
)
from app.modules.prompts.service import get_active_prompt

log = structlog.get_logger()

MOTOR_MODEL_MAP = {
    "gemini": OpenRouterClient.MODELS["gemini"],
    "claude": OpenRouterClient.MODELS["claude"],
}


@asynccontextmanager
async def _get_session(db: AsyncSession | None):
    if db is not None:
        yield db
    else:
        async with async_session() as new_db:
            yield new_db


async def _check_all_sections_done(
    db: AsyncSession, project_id: str
) -> None:
    result = await db.execute(
        select(CompendiumSection).where(
            CompendiumSection.project_id == project_id
        )
    )
    all_sections = list(result.scalars().all())

    if len(all_sections) < 11:
        return

    all_done = all(
        s.status in (SectionStatus.COMPLETED, SectionStatus.FAILED)
        for s in all_sections
    )

    if not all_done:
        return

    project_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        return

    if project.status == ProjectStatus.GENERATING:
        project.set_status(ProjectStatus.REVIEW)
        await db.commit()
        log.info(
            "project_transitioned_to_review",
            project_id=str(project.id),
        )


async def generate_section(
    ctx: dict,
    project_id: str,
    section_number: int,
    _db: AsyncSession | None = None,
) -> dict:
    async with _get_session(_db) as db:
        project_result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if project is None:
            return {"status": "error", "detail": "Project not found"}

        section_result = await db.execute(
            select(CompendiumSection).where(
                CompendiumSection.project_id == project_id,
                CompendiumSection.section_number == section_number,
            )
        )
        section = section_result.scalar_one_or_none()
        if section is None:
            return {"status": "error", "detail": "Section not found"}

        section.status = SectionStatus.PROCESSING
        await db.commit()

        try:
            config = SECTION_CONFIGS[section_number]
            model_id = MOTOR_MODEL_MAP[config.motor]

            system_prompt_rec = await get_active_prompt(
                db, "system_prompt_sam_v9"
            )

            patch_gemini = None
            if config.motor == "gemini":
                patch_rec = await get_active_prompt(
                    db, "patch_gemini_density"
                )
                patch_gemini = patch_rec.content

            source_filenames = []
            for doc in project.documents:
                source_filenames.append(doc.filename)
            source_filename = ", ".join(source_filenames) if source_filenames else "N/A"

            prompt = build_section_prompt(
                section_number=section_number,
                merged_content=project.merged_content or "",
                pathology_name=project.name,
                source_filename=source_filename,
                is_first=(section_number == 1),
                is_last=(section_number == 11),
                system_prompt=system_prompt_rec.content,
                patch_gemini=patch_gemini,
            )

            ai = OpenRouterClient()
            ai_result = await ai.generate(
                prompt=prompt,
                model=model_id,
                temperature=0.1,
                max_tokens=65536,
            )

            section.content = ai_result.content
            section.model_used = ai_result.model
            section.input_tokens = ai_result.input_tokens
            section.output_tokens = ai_result.output_tokens
            section.cost_usd = ai_result.cost_usd
            section.prompt_version = str(system_prompt_rec.version)
            section.status = SectionStatus.COMPLETED
            await db.commit()

            log.info(
                "section_generated",
                section_id=str(section.id),
                project_id=project_id,
                section_number=section_number,
                model=ai_result.model,
                input_tokens=ai_result.input_tokens,
                output_tokens=ai_result.output_tokens,
                cost_usd=float(ai_result.cost_usd) if ai_result.cost_usd else 0.0,
            )

            await _check_all_sections_done(db, project_id)

            return {"status": "completed", "section_id": str(section.id)}

        except Exception as exc:
            section.status = SectionStatus.FAILED
            section.error_message = str(exc)
            await db.commit()

            log.error(
                "section_generation_failed",
                section_id=str(section.id),
                project_id=project_id,
                section_number=section_number,
                error=str(exc),
            )

            await _check_all_sections_done(db, project_id)

            return {"status": "failed", "error": str(exc)}
