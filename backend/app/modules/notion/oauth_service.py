import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.notion_config import NotionConfig
from app.models.user import User


@dataclass
class NotionTokenResponse:
    access_token: str
    refresh_token: str | None
    token_type: str
    workspace_id: str
    workspace_name: str | None
    workspace_icon: str | None
    bot_id: str
    owner: dict
    duplicated_template_id: str | None


def resolve_oauth_redirect_uri() -> str:
    """Public callback URL Notion must redirect to (via nginx on FRONTEND_URL)."""
    if settings.notion_oauth_redirect_uri:
        return settings.notion_oauth_redirect_uri.rstrip("/")
    base = (settings.frontend_url or "").rstrip("/")
    if not base:
        return ""
    return f"{base}/api/v1/notion/oauth/callback"


def assert_oauth_configured() -> None:
    """Raise if Notion OAuth env vars are missing (avoids Notion opaque errors)."""
    from fastapi import HTTPException, status

    if not settings.notion_oauth_client_id or not settings.notion_oauth_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Notion OAuth no está configurado en el servidor. "
                "Define NOTION_OAUTH_CLIENT_ID y NOTION_OAUTH_CLIENT_SECRET "
                "y registra en Notion el Redirect URI: "
                f"{resolve_oauth_redirect_uri() or '{FRONTEND_URL}/api/v1/notion/oauth/callback'}"
            ),
        )
    if not resolve_oauth_redirect_uri():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Falta NOTION_OAUTH_REDIRECT_URI o FRONTEND_URL. "
                "En producción: https://tu-dominio/api/v1/notion/oauth/callback"
            ),
        )


def build_authorize_url(state: str) -> str:
    """Build the Notion OAuth authorize URL."""
    assert_oauth_configured()
    params = {
        "owner": "user",
        "client_id": settings.notion_oauth_client_id,
        "redirect_uri": resolve_oauth_redirect_uri(),
        "response_type": "code",
        "state": state,
    }
    return f"https://api.notion.com/v1/oauth/authorize?{urlencode(params)}"


async def exchange_code(code: str) -> NotionTokenResponse:
    """Exchange an authorization code for an access token.

    Uses HTTP Basic auth with client_id:client_secret as per Notion docs.
    """
    credentials = base64.b64encode(
        f"{settings.notion_oauth_client_id}:{settings.notion_oauth_client_secret}".encode()
    ).decode()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.notion.com/v1/oauth/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
                "Notion-Version": "2026-03-11",
            },
             json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": resolve_oauth_redirect_uri(),
            },
            timeout=30.0,
        )

    if resp.status_code != 200:
        raise Exception(
            f"Notion OAuth token exchange failed ({resp.status_code}): {resp.text}"
        )

    data = resp.json()
    owner = data.get("owner", {})
    owner_info = {}
    if isinstance(owner, dict):
        if owner.get("type") == "user":
            user_data = owner.get("user", {})
            owner_info = {
                "user_id": user_data.get("id", ""),
                "email": user_data.get("person", {}).get("email", ""),
            }
        elif owner.get("type") == "workspace":
            owner_info = {"user_id": "", "email": ""}

    return NotionTokenResponse(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        token_type=data.get("token_type", "bearer"),
        workspace_id=data["workspace_id"],
        workspace_name=data.get("workspace_name"),
        workspace_icon=data.get("workspace_icon"),
        bot_id=data["bot_id"],
        owner=owner_info,
        duplicated_template_id=data.get("duplicated_template_id"),
    )


async def refresh_access_token(refresh_token: str) -> NotionTokenResponse:
    """Refresh an expired access token using the refresh_token grant."""
    credentials = base64.b64encode(
        f"{settings.notion_oauth_client_id}:{settings.notion_oauth_client_secret}".encode()
    ).decode()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.notion.com/v1/oauth/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
                "Notion-Version": "2026-03-11",
            },
            json={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=30.0,
        )

    if resp.status_code != 200:
        raise Exception(
            f"Notion token refresh failed ({resp.status_code}): {resp.text}"
        )

    data = resp.json()
    owner = data.get("owner", {})
    owner_info = {}
    if isinstance(owner, dict):
        if owner.get("type") == "user":
            user_data = owner.get("user", {})
            owner_info = {
                "user_id": user_data.get("id", ""),
                "email": user_data.get("person", {}).get("email", ""),
            }
        elif owner.get("type") == "workspace":
            owner_info = {"user_id": "", "email": ""}

    return NotionTokenResponse(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        token_type=data.get("token_type", "bearer"),
        workspace_id=data["workspace_id"],
        workspace_name=data.get("workspace_name"),
        workspace_icon=data.get("workspace_icon"),
        bot_id=data["bot_id"],
        owner=owner_info,
        duplicated_template_id=data.get("duplicated_template_id"),
    )


async def save_oauth_result(
    db: AsyncSession,
    user: User,
    token_data: NotionTokenResponse,
) -> NotionConfig:
    """Persist OAuth tokens in NotionConfig for the given user."""
    result = await db.execute(
        select(NotionConfig).where(NotionConfig.user_id == user.id)
    )
    config = result.scalar_one_or_none()

    if config is None:
        config = NotionConfig(user_id=str(user.id))
        db.add(config)

    config.access_token = token_data.access_token
    config.refresh_token = token_data.refresh_token
    config.workspace_name = token_data.workspace_name
    config.workspace_id = token_data.workspace_id
    config.bot_id = token_data.bot_id
    config.owner_user_id = token_data.owner.get("user_id")
    config.owner_email = token_data.owner.get("email")
    config.is_connected = True
    config.connected_at = datetime.now(timezone.utc)
    config.last_refreshed_at = datetime.now(timezone.utc)
    config.token_expires_at = None

    await db.commit()
    await db.refresh(config)
    return config


async def try_refresh_token(
    db: AsyncSession,
    config: NotionConfig,
) -> bool:
    """Attempt to refresh the access token.

    Returns True if refresh succeeded, False if refresh failed (user must reconnect).
    """
    if not config.refresh_token:
        return False

    try:
        token_data = await refresh_access_token(config.refresh_token)
    except Exception:
        return False

    config.access_token = token_data.access_token
    if token_data.refresh_token:
        config.refresh_token = token_data.refresh_token
    config.last_refreshed_at = datetime.now(timezone.utc)

    await db.commit()
    return True
