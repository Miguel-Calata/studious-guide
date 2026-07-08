from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.modules.auth.dependencies import get_current_user
from app.modules.compendiums.dependencies import get_project_for_compendium
from app.modules.notion.dependencies import get_notion_config
from app.modules.notion.schemas import (
    NotionConfigUpdate,
    NotionConnectRequest,
    NotionSearchResult,
    NotionStatusResponse,
    PublishNotionRequest,
    PublishNotionResponse,
)
from app.modules.notion.service import (
    connect_notion,
    publish_compendium_to_notion,
    search_pages,
    update_notion_config,
)
from app.modules.notion.service import (
    get_notion_config as get_config_service,
)

router = APIRouter(tags=["Notion"])


@router.post(
    "/notion/connect",
    response_model=NotionStatusResponse,
)
async def connect(
    body: NotionConnectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    config = await connect_notion(db, current_user, body.api_key)
    return {
        "is_connected": config.is_connected,
        "workspace_name": config.workspace_name,
        "default_parent_page_id": config.default_parent_page_id,
    }


@router.get(
    "/notion/status",
    response_model=NotionStatusResponse,
)
async def status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    config = await get_config_service(db, current_user)
    if config is None:
        return {
            "is_connected": False,
            "workspace_name": None,
            "default_parent_page_id": None,
        }
    return {
        "is_connected": config.is_connected,
        "workspace_name": config.workspace_name,
        "default_parent_page_id": config.default_parent_page_id,
    }


@router.get(
    "/notion/search",
    response_model=list[NotionSearchResult],
)
async def search(
    query: str = "",
    config=Depends(get_notion_config),
) -> list[dict]:
    return await search_pages(config, query)


@router.put(
    "/notion/config",
    response_model=NotionStatusResponse,
)
async def update_config(
    body: NotionConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    config = await update_notion_config(db, current_user, body)
    return {
        "is_connected": config.is_connected,
        "workspace_name": config.workspace_name,
        "default_parent_page_id": config.default_parent_page_id,
    }


@router.post(
    "/projects/{project_id}/publish/notion",
    response_model=PublishNotionResponse,
)
async def publish(
    body: PublishNotionRequest | None = None,
    project=Depends(get_project_for_compendium),
    db: AsyncSession = Depends(get_db),
    config=Depends(get_notion_config),
) -> dict:
    parent_page_id = body.parent_page_id if body else None
    return await publish_compendium_to_notion(db, project, config, parent_page_id)
