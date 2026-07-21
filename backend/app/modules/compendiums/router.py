from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_arq_pool
from app.models.compendium_section import CompendiumSection
from app.models.project import Project
from app.models.user import User
from app.modules.auth.dependencies import get_current_user
from app.modules.compendiums.dependencies import (
    get_project_for_compendium,
    get_section_or_404,
)
from app.modules.compendiums.schemas import (
    GenerateRequest,
    GenerateResponse,
    MergeResponse,
    SectionResponse,
    SectionUpdate,
)
from app.modules.compendiums.service import (
    generate_sections,
    get_sections_for_project,
    merge_extractions,
    regenerate_section,
    update_section,
)

router = APIRouter(tags=["Compendiums"])


@router.post(
    "/projects/{project_id}/merge",
    response_model=MergeResponse,
)
async def merge(
    project: Project = Depends(get_project_for_compendium),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis | None = Depends(get_arq_pool),
) -> dict:
    result = await merge_extractions(db, project, arq_pool)
    proj = result["project"]
    return {
        "project_id": str(proj.id),
        "merged_char_count": len(proj.merged_content or ""),
        "extraction_count": proj.merged_content.count("\n\n") + 1 if proj.merged_content else 0,
        "project_status": proj.status,
        "warnings": result.get("warnings", []),
        "ecos_map_enqueued": result.get("ecos_map_enqueued", False),
    }


@router.post(
    "/projects/{project_id}/generate",
    response_model=GenerateResponse,
)
async def generate(
    body: GenerateRequest | None = None,
    project: Project = Depends(get_project_for_compendium),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis | None = Depends(get_arq_pool),
) -> dict:
    model_overrides: dict | None = None
    if body:
        model_overrides = {}
        if body.gemini_model:
            model_overrides["gemini"] = body.gemini_model
        if body.claude_model:
            model_overrides["claude"] = body.claude_model
        if not model_overrides:
            model_overrides = None
    return await generate_sections(db, project, arq_pool, model_overrides)


@router.get(
    "/projects/{project_id}/sections",
    response_model=list[SectionResponse],
)
async def list_sections(
    project: Project = Depends(get_project_for_compendium),
    db: AsyncSession = Depends(get_db),
) -> list[CompendiumSection]:
    return await get_sections_for_project(db, str(project.id))


@router.get(
    "/sections/{section_id}",
    response_model=SectionResponse,
)
async def get_one(
    section: CompendiumSection = Depends(get_section_or_404),
) -> CompendiumSection:
    return section


@router.put(
    "/sections/{section_id}",
    response_model=SectionResponse,
)
async def update_one(
    body: SectionUpdate,
    section: CompendiumSection = Depends(get_section_or_404),
    db: AsyncSession = Depends(get_db),
) -> CompendiumSection:
    return await update_section(db, section, body.content)


@router.post(
    "/sections/{section_id}/regenerate",
    response_model=SectionResponse,
)
async def regenerate_one(
    body: GenerateRequest | None = None,
    section: CompendiumSection = Depends(get_section_or_404),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis | None = Depends(get_arq_pool),
) -> CompendiumSection:
    model_overrides: dict | None = None
    if body:
        model_overrides = {}
        if body.gemini_model:
            model_overrides["gemini"] = body.gemini_model
        if body.claude_model:
            model_overrides["claude"] = body.claude_model
        if not model_overrides:
            model_overrides = None
    return await regenerate_section(db, section, arq_pool, model_overrides)
