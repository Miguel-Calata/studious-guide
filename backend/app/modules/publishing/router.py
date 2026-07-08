from fastapi import APIRouter, Depends, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_storage
from app.models.project import Project
from app.modules.publishing.dependencies import get_project_for_publish
from app.modules.publishing.schemas import (
    PublicCompendiumDetail,
    PublicCompendiumListItem,
    PublicSectionResponse,
    PublishResponse,
)
from app.modules.publishing.service import (
    download_compendium,
    get_public_compendium,
    get_public_section,
    list_public_compendiums,
    publish_compendium,
)
from app.services.storage import StorageBackend

router = APIRouter(tags=["Publishing"])
public_router = APIRouter(tags=["Public Viewer"])


@router.post(
    "/projects/{project_id}/publish",
    response_model=PublishResponse,
)
async def publish(
    project: Project = Depends(get_project_for_publish),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> dict:
    return await publish_compendium(db, project, storage)


@public_router.get(
    "/public/compendiums",
    response_model=list[PublicCompendiumListItem],
)
async def list_published(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_public_compendiums(db)


@public_router.get(
    "/public/compendiums/{slug}",
    response_model=PublicCompendiumDetail,
)
async def get_detail(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_public_compendium(db, slug)


@public_router.get(
    "/public/compendiums/{slug}/download",
    response_class=PlainTextResponse,
)
async def download(
    slug: str,
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> Response:
    filename, content = await download_compendium(db, slug, storage)
    return PlainTextResponse(
        content=content.decode("utf-8"),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/markdown; charset=utf-8",
        },
    )


@public_router.get(
    "/public/compendiums/{slug}/sections/{section_number}",
    response_model=PublicSectionResponse,
)
async def get_section(
    slug: str,
    section_number: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    section = await get_public_section(db, slug, section_number)
    return {
        "section_number": section.section_number,
        "section_name": section.section_name,
        "content": section.content,
        "dosification": section.dosification,
    }
