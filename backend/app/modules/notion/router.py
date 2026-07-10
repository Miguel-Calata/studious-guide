from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.modules.auth.dependencies import get_current_user
from app.modules.compendiums.dependencies import get_project_for_compendium
from app.modules.notion.dependencies import get_notion_config
from app.modules.notion.oauth_service import (
    assert_oauth_configured,
    build_authorize_url,
    exchange_code,
    save_oauth_result,
)
from app.modules.notion.oauth_state import (
    clear_state_cookie,
    issue_state,
    sanitize_return_to,
    set_state_cookie,
    verify_state,
)
from app.modules.notion.schemas import (
    ExportPublicNotionResponse,
    NotionConfigUpdate,
    NotionOAuthStartResponse,
    NotionSearchResult,
    NotionStatusResponse,
    PublishNotionRequest,
    PublishNotionResponse,
)
from app.modules.notion.service import (
    disconnect_notion,
    export_public_note_to_notion,
    get_notion_config as get_config_service,
    needs_reconnect,
    publish_compendium_to_notion,
    search_pages,
    update_notion_config,
)

router = APIRouter(tags=["Notion"])

_DEFAULT_RETURN_TO = "/app"


def _frontend_redirect(path: str, **query: str) -> str:
    base = settings.frontend_url.rstrip("/")
    safe_path = sanitize_return_to(path)
    qs = "&".join(f"{k}={quote(str(v), safe='')}" for k, v in query.items() if v is not None)
    return f"{base}{safe_path}?{qs}" if qs else f"{base}{safe_path}"


@router.get(
    "/notion/oauth/start",
    response_model=NotionOAuthStartResponse,
)
async def oauth_start(
    return_to: str | None = Query(None),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Generate the Notion OAuth authorize URL and a signed state token.

    The frontend should redirect the user's browser to the returned URL.
    Optional return_to is a relative path (e.g. /compendiums/slug) for post-OAuth redirect.
    """
    assert_oauth_configured()
    state = issue_state(str(current_user.id), return_to=return_to)
    authorize_url = build_authorize_url(state)
    response = JSONResponse(content={"authorize_url": authorize_url})
    set_state_cookie(response, state)
    return response


@router.get("/notion/oauth/callback")
async def oauth_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle the OAuth redirect from Notion.

    Validates state + cookie, exchanges the code for tokens, persists them,
    and redirects the browser back to the frontend.

    code/state are optional so missing/error callbacks redirect to the SPA
    instead of returning a FastAPI validation JSON on the API path.
    """
    return_to = _DEFAULT_RETURN_TO

    def _error_redirect(msg: str, path: str = _DEFAULT_RETURN_TO) -> RedirectResponse:
        response = RedirectResponse(
            url=_frontend_redirect(path, notion="error", msg=msg[:200]),
            status_code=status.HTTP_302_FOUND,
        )
        clear_state_cookie(response)
        return response

    # Notion denied or sent an OAuth error.
    if error:
        msg = error_description or error or "Notion denegó la autorización"
        return _error_redirect(msg)

    if not code or not state:
        return _error_redirect(
            "OAuth incompleto: falta code o state. "
            "Vuelve a pulsar «Añadir a Notion» o «Conectar con Notion»."
        )

    # 1. Validate state (CSRF) — also extracts user_id and return_to.
    try:
        user_id, return_to = verify_state(state, request)
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        return _error_redirect(str(detail))

    # 2. Exchange code → token (uses HTTP Basic with client_id:client_secret).
    try:
        token_data = await exchange_code(code)
    except Exception as exc:
        return _error_redirect(str(exc)[:200], return_to)

    # 3. Look up the user.
    from sqlalchemy import select as sa_select
    from app.models.user import User as UserModel

    result = await db.execute(sa_select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return _error_redirect("Usuario no encontrado", return_to)

    # 4. Persist tokens.
    try:
        await save_oauth_result(db, user, token_data)
    except Exception:
        return _error_redirect("Error guardando tokens", return_to)

    # 5. Clear state cookie and redirect to frontend.
    response = RedirectResponse(
        url=_frontend_redirect(return_to, notion="connected"),
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


@router.post(
    "/public/compendiums/{slug}/export/notion",
    response_model=ExportPublicNotionResponse,
)
async def export_public_to_notion(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Export a published public note into the current user's Notion workspace."""
    return await export_public_note_to_notion(db, current_user, slug)
