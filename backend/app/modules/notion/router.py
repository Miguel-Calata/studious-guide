from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.modules.auth.dependencies import get_current_user
from app.modules.compendiums.dependencies import get_project_for_compendium
from app.modules.notion.dependencies import get_notion_config
from app.modules.notion.oauth_service import build_authorize_url, exchange_code, save_oauth_result
from app.modules.notion.oauth_state import issue_state, set_state_cookie, clear_state_cookie, verify_state
from app.modules.notion.schemas import (
    NotionConfigUpdate,
    NotionOAuthStartResponse,
    NotionSearchResult,
    NotionStatusResponse,
    PublishNotionRequest,
    PublishNotionResponse,
)
from app.modules.notion.service import (
    disconnect_notion,
    get_notion_config as get_config_service,
    needs_reconnect,
    publish_compendium_to_notion,
    search_pages,
    update_notion_config,
)

router = APIRouter(tags=["Notion"])

# Frontend URL to redirect to after OAuth callback (query ?notion=connected or ?notion=error&msg=...).
_FRONTEND_CALLBACK_PATH = "/settings/notion"


@router.get(
    "/notion/oauth/start",
    response_model=NotionOAuthStartResponse,
)
async def oauth_start(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Generate the Notion OAuth authorize URL and a signed state token.

    The frontend should redirect the user's browser to the returned URL.
    """
    state = issue_state(str(current_user.id))
    authorize_url = build_authorize_url(state)
    response = Response()
    set_state_cookie(response, state)
    return {"authorize_url": authorize_url}


@router.get("/notion/oauth/callback")
async def oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle the OAuth redirect from Notion.

    Validates state + cookie, exchanges the code for tokens, persists them,
    and redirects the browser back to the frontend.
    """
    # 1. Validate state (CSRF) — also extracts user_id.
    user_id = verify_state(state, request)

    # 2. Exchange code → token (uses HTTP Basic with client_id:client_secret).
    try:
        token_data = await exchange_code(code)
    except Exception as exc:
        return RedirectResponse(
            url=f"{_FRONTEND_CALLBACK_PATH}?notion=error&msg={str(exc)[:200]}",
            status_code=status.HTTP_302_FOUND,
        )

    # 3. Look up the user.
    from sqlalchemy import select as sa_select
    from app.models.user import User as UserModel

    result = await db.execute(sa_select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return RedirectResponse(
            url=f"{_FRONTEND_CALLBACK_PATH}?notion=error&msg=Usuario+no+encontrado",
            status_code=status.HTTP_302_FOUND,
        )

    # 4. Persist tokens.
    try:
        await save_oauth_result(db, user, token_data)
    except Exception as exc:
        return RedirectResponse(
            url=f"{_FRONTEND_CALLBACK_PATH}?notion=error&msg=Error+guardando+tokens",
            status_code=status.HTTP_302_FOUND,
        )

    # 5. Clear state cookie and redirect to frontend.
    response = RedirectResponse(
        url=f"{_FRONTEND_CALLBACK_PATH}?notion=connected",
        status_code=status.HTTP_302_FOUND,
    )
    clear_state_cookie(response)
    return response


@router.get(
    "/notion/status",
    response_model=NotionStatusResponse,
)
async def get_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    config = await get_config_service(db, current_user)
    if config is None:
        return {
            "is_connected": False,
            "needs_reconnect": False,
            "workspace_name": None,
            "workspace_id": None,
            "owner_email": None,
            "connected_at": None,
            "default_parent_page_id": None,
        }
    return {
        "is_connected": config.is_connected,
        "needs_reconnect": needs_reconnect(config),
        "workspace_name": config.workspace_name,
        "workspace_id": config.workspace_id,
        "owner_email": config.owner_email,
        "connected_at": config.connected_at.isoformat() if config.connected_at else None,
        "default_parent_page_id": config.default_parent_page_id,
    }


@router.post(
    "/notion/disconnect",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def disconnect(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await disconnect_notion(db, current_user)


@router.get(
    "/notion/search",
    response_model=list[NotionSearchResult],
)
async def search(
    query: str = "",
    config=Depends(get_notion_config),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await search_pages(db, config, query)


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
        "needs_reconnect": needs_reconnect(config),
        "workspace_name": config.workspace_name,
        "workspace_id": config.workspace_id,
        "owner_email": config.owner_email,
        "connected_at": config.connected_at.isoformat() if config.connected_at else None,
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
