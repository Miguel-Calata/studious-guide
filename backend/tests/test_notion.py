import io
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select, update

from app.models.compendium_section import CompendiumSection, SectionStatus
from app.models.extraction import Extraction, ExtractionStatus
from app.models.notion_config import NotionConfig
from app.models.project import Project, ProjectStatus
from app.models.source_document import SourceDocument


def _make_mock_settings(**overrides):
    """Create a mock settings object with sensible defaults for Notion OAuth tests."""
    defaults = {
        "notion_oauth_client_id": "test-client-id",
        "notion_oauth_client_secret": "test-client-secret",
        "notion_oauth_redirect_uri": "http://localhost:8000/api/v1/notion/oauth/callback",
        "notion_oauth_state_cookie_name": "notion_oauth_state",
        "notion_oauth_state_ttl_seconds": 300,
        "cookie_secure": False,
        "cookie_samesite": "lax",
        "cookie_domain": None,
        "secret_key": "test-secret-key-for-oauth",
        "access_token_expire_minutes": 60,
        "refresh_token_expire_days": 7,
        "frontend_url": "http://localhost:5173",
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock
from app.modules.notion.oauth_state import issue_state


async def _register_and_login(client, email: str, password: str = "Test1234"):
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return login.json()["access_token"]


async def _create_project(client, token: str, name: str = "Notion Project"):
    response = await client.post(
        "/api/v1/projects",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()["id"]


async def _upload_document(client, token: str, project_id: str):
    response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"files": ("test.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()["documents"][0]["id"]


async def _create_extraction(client, token: str, document_id: str):
    response = await client.post(
        f"/api/v1/documents/{document_id}/extract",
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()["id"]


async def _complete_extraction(
    db_session,
    extraction_id: str,
    content: str = "Extracted clinical content",
):
    await db_session.execute(
        update(Extraction)
        .where(Extraction.id == extraction_id)
        .values(status=ExtractionStatus.COMPLETED, content=content)
    )

    extraction = (
        await db_session.execute(
            select(Extraction).where(Extraction.id == extraction_id)
        )
    ).scalar_one()
    doc = (
        await db_session.execute(
            select(SourceDocument).where(
                SourceDocument.id == extraction.source_document_id
            )
        )
    ).scalar_one()

    result = await db_session.execute(
        select(Extraction)
        .join(SourceDocument, SourceDocument.id == Extraction.source_document_id)
        .where(SourceDocument.project_id == doc.project_id)
    )
    all_extractions = list(result.scalars().all())
    all_done = all(
        e.status in (ExtractionStatus.COMPLETED, ExtractionStatus.FAILED)
        for e in all_extractions
    )

    if all_done:
        project = (
            await db_session.execute(
                select(Project).where(Project.id == doc.project_id)
            )
        ).scalar_one()
        if project.status == ProjectStatus.EXTRACTING:
            project.status = ProjectStatus.DRAFT

    await db_session.commit()


async def _setup_compendium(client, token, project_id, db_session):
    doc = await _upload_document(client, token, project_id)
    ext = await _create_extraction(client, token, doc)
    await _complete_extraction(db_session, ext, "Clinical content")

    await client.post(
        f"/api/v1/projects/{project_id}/merge",
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/api/v1/projects/{project_id}/generate",
        headers={"Authorization": f"Bearer {token}"},
    )

    sections = (
        await db_session.execute(
            select(CompendiumSection)
            .where(CompendiumSection.project_id == project_id)
            .order_by(CompendiumSection.section_number)
        )
    ).scalars().all()

    for section in sections:
        section.status = SectionStatus.COMPLETED
        section.content = (
            f"## {section.section_name}\n\n"
            f"Content for section {section.section_number}"
        )
    await db_session.commit()

    await db_session.execute(
        update(Project)
        .where(Project.id == project_id)
        .values(status=ProjectStatus.REVIEW)
    )
    await db_session.commit()


async def _create_notion_config(
    db_session,
    user_id: str,
    connected: bool = True,
    with_refresh: bool = True,
    expired: bool = False,
):
    config = NotionConfig(user_id=user_id)
    config.access_token = "ntn_oauth_access_token_12345"
    if with_refresh:
        config.refresh_token = "ntn_oauth_refresh_token_67890"
    config.workspace_name = "Test Workspace"
    config.workspace_id = "ws-001"
    config.bot_id = "bot-001"
    config.owner_user_id = "notion-user-001"
    config.owner_email = "dr@test.com"
    config.default_parent_page_id = "parent-page-123"
    config.is_connected = connected
    config.connected_at = datetime.now(timezone.utc)
    config.last_refreshed_at = datetime.now(timezone.utc)
    if expired:
        config.token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    else:
        config.token_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    db_session.add(config)
    await db_session.commit()
    await db_session.refresh(config)
    return config


# ─── OAuth Start ───


@pytest.mark.asyncio
async def test_oauth_start_returns_authorize_url(client, db_session):
    token = await _register_and_login(client, "notion-oauth-start@test.com")
    mock_settings = _make_mock_settings()

    with patch("app.modules.notion.oauth_state.settings", mock_settings), \
         patch("app.modules.notion.oauth_service.settings", mock_settings):
        response = await client.get(
            "/api/v1/notion/oauth/start",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "authorize_url" in data
    assert "api.notion.com/v1/oauth/authorize" in data["authorize_url"]
    assert "client_id=test-client-id" in data["authorize_url"]
    assert "state=" in data["authorize_url"]


# ─── OAuth Callback ───


@pytest.mark.asyncio
async def test_oauth_callback_invalid_state_redirects_to_frontend(client, db_session):
    mock_settings = _make_mock_settings()
    with patch("app.modules.notion.router.settings", mock_settings), \
         patch("app.modules.notion.oauth_state.settings", mock_settings):
        response = await client.get(
            "/api/v1/notion/oauth/callback?code=abc&state=bad",
            follow_redirects=False,
        )
    assert response.status_code == 302
    loc = response.headers["location"]
    assert "notion=error" in loc
    assert loc.startswith("http://localhost:5173/")


@pytest.mark.asyncio
async def test_oauth_callback_missing_params_redirects_to_frontend(client, db_session):
    mock_settings = _make_mock_settings()
    with patch("app.modules.notion.router.settings", mock_settings):
        response = await client.get(
            "/api/v1/notion/oauth/callback",
            follow_redirects=False,
        )
    assert response.status_code == 302
    loc = response.headers["location"]
    assert "notion=error" in loc
    assert "code" in loc or "OAuth" in loc or "msg=" in loc


@pytest.mark.asyncio
async def test_oauth_callback_success_persists_tokens(client, db_session):
    token = await _register_and_login(client, "notion-oauth-cb@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    mock_settings = _make_mock_settings()

    mock_token_response = {
        "access_token": "ntn_new_access",
        "refresh_token": "ntn_new_refresh",
        "token_type": "bearer",
        "workspace_id": "ws-new",
        "workspace_name": "Mi Workspace",
        "workspace_icon": None,
        "bot_id": "bot-new",
        "owner": {
            "type": "user",
            "user": {
                "id": "notion-uid",
                "object": "user",
                "name": "Dr. Test",
                "avatar_url": None,
                "type": "person",
                "person": {"email": "dr@test.com"},
            },
        },
        "duplicated_template_id": None,
        "request_id": "req-123",
    }

    with patch("app.modules.notion.oauth_state.settings", mock_settings), \
         patch("app.modules.notion.oauth_service.settings", mock_settings), \
         patch("app.modules.notion.router.settings", mock_settings), \
         patch(
             "app.modules.notion.oauth_service.httpx.AsyncClient"
         ) as mock_client_cls:
        state = issue_state(user_id)
        mock_http = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_token_response
        mock_http.post = AsyncMock(return_value=mock_resp)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_http

        client.cookies.set("notion_oauth_state", state)
        response = await client.get(
            f"/api/v1/notion/oauth/callback?code=authcode&state={state}",
            follow_redirects=False,
        )

    assert response.status_code == 302
    loc = response.headers["location"]
    assert "notion=connected" in loc
    assert loc.startswith("http://localhost:5173/")

    result = await db_session.execute(
        select(NotionConfig).where(NotionConfig.user_id == user_id)
    )
    config = result.scalar_one_or_none()
    assert config is not None
    assert config.is_connected is True
    assert config.access_token == "ntn_new_access"
    assert config.refresh_token == "ntn_new_refresh"
    assert config.workspace_id == "ws-new"


# ─── Status ───


@pytest.mark.asyncio
async def test_status_connected(client, db_session):
    token = await _register_and_login(client, "notion-status-conn@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    await _create_notion_config(db_session, user_id, connected=True)

    response = await client.get(
        "/api/v1/notion/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_connected"] is True
    assert data["workspace_name"] == "Test Workspace"
    assert data["default_parent_page_id"] == "parent-page-123"
    assert data["needs_reconnect"] is False
    assert data["owner_email"] == "dr@test.com"


@pytest.mark.asyncio
async def test_status_disconnected(client, db_session):
    token = await _register_and_login(client, "notion-status-disc@test.com")
    response = await client.get(
        "/api/v1/notion/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_connected"] is False
    assert data["needs_reconnect"] is False


@pytest.mark.asyncio
async def test_status_needs_reconnect_when_expired_no_refresh(client, db_session):
    token = await _register_and_login(client, "notion-reconnect@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    await _create_notion_config(
        db_session, user_id, connected=True, with_refresh=False, expired=True
    )

    response = await client.get(
        "/api/v1/notion/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_connected"] is True
    assert data["needs_reconnect"] is True


# ─── Disconnect ───


@pytest.mark.asyncio
async def test_disconnect_clears_tokens(client, db_session):
    token = await _register_and_login(client, "notion-disconnect@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    await _create_notion_config(db_session, user_id, connected=True)

    response = await client.post(
        "/api/v1/notion/disconnect",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204

    result = await db_session.execute(
        select(NotionConfig).where(NotionConfig.user_id == user_id)
    )
    config = result.scalar_one()
    assert config.is_connected is False
    assert config.refresh_token_encrypted is None


# ─── Search ───


@pytest.mark.asyncio
async def test_search_pages(client, db_session):
    token = await _register_and_login(client, "notion-search@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    await _create_notion_config(db_session, user_id, connected=True)

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.search = AsyncMock(
            return_value=[
                {"id": "page-1", "title": "Compendios SAM", "object": "page"},
                {"id": "page-2", "title": "Otra página", "object": "page"},
            ]
        )

        response = await client.get(
            "/api/v1/notion/search?query=Compendios",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 2
    assert results[0]["title"] == "Compendios SAM"


# ─── Publish ───


@pytest.mark.asyncio
async def test_publish_creates_pages(client, db_session):
    token = await _register_and_login(client, "notion-publish@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    await _create_notion_config(db_session, user_id, connected=True)
    project_id = await _create_project(client, token, "Lesión Renal Aguda")
    await _setup_compendium(client, token, project_id, db_session)

    created_pages = []

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.create_page = AsyncMock(
            side_effect=lambda parent_page_id, title, content_markdown: (
                created_pages.append(title) or f"page-{len(created_pages)}"
            )
        )

        response = await client.post(
            f"/api/v1/projects/{project_id}/publish/notion",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    assert len(data["sections_published"]) == 11
    assert "compendium_page_id" in data

    result = await db_session.execute(
        select(CompendiumSection).where(
            CompendiumSection.project_id == project_id
        )
    )
    sections = list(result.scalars().all())
    for s in sections:
        assert s.notion_page_id is not None


@pytest.mark.asyncio
async def test_publish_updates_existing(client, db_session):
    token = await _register_and_login(client, "notion-republish@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    await _create_notion_config(db_session, user_id, connected=True)
    project_id = await _create_project(client, token, "Republish Test")
    await _setup_compendium(client, token, project_id, db_session)

    result = await db_session.execute(
        select(CompendiumSection).where(
            CompendiumSection.project_id == project_id
        )
    )
    sections = list(result.scalars().all())
    for i, s in enumerate(sections):
        s.notion_page_id = f"existing-page-{i}"
    await db_session.commit()

    update_called = []
    create_called = []

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.create_page = AsyncMock(
            side_effect=lambda parent_page_id, title, content_markdown: (
                create_called.append(title) or f"new-page-{len(create_called)}"
            )
        )
        mock_wrapper.update_page = AsyncMock(
            side_effect=lambda page_id, md: update_called.append(page_id)
        )

        response = await client.post(
            f"/api/v1/projects/{project_id}/publish/notion",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert len(create_called) == 1
    assert len(update_called) == 11
    assert all(p.startswith("existing-page-") for p in update_called)


@pytest.mark.asyncio
async def test_publish_fails_without_connection(client, db_session):
    token = await _register_and_login(client, "notion-noconn@test.com")
    project_id = await _create_project(client, token)
    await _setup_compendium(client, token, project_id, db_session)

    response = await client.post(
        f"/api/v1/projects/{project_id}/publish/notion",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_publish_auto_refreshes_expired_token(client, db_session):
    token = await _register_and_login(client, "notion-refresh@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    await _create_notion_config(
        db_session, user_id, connected=True, with_refresh=True, expired=True
    )
    project_id = await _create_project(client, token, "Refresh Test")
    await _setup_compendium(client, token, project_id, db_session)

    mock_refresh_response = {
        "access_token": "ntn_refreshed_access",
        "refresh_token": "ntn_new_refresh",
        "token_type": "bearer",
        "workspace_id": "ws-001",
        "workspace_name": "Test Workspace",
        "workspace_icon": None,
        "bot_id": "bot-001",
        "owner": {
            "type": "user",
            "user": {
                "id": "notion-uid",
                "object": "user",
                "name": "Dr. Test",
                "avatar_url": None,
                "type": "person",
                "person": {"email": "dr@test.com"},
            },
        },
        "duplicated_template_id": None,
        "request_id": "req-123",
    }

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls, \
        patch(
            "app.modules.notion.oauth_service.settings"
        ) as mock_oauth_settings, \
        patch(
            "app.modules.notion.oauth_service.httpx.AsyncClient"
        ) as mock_client_cls:
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.create_page = AsyncMock(
            side_effect=lambda parent_page_id, title, content_markdown: "page-new"
        )

        mock_oauth_settings.notion_oauth_client_id = "cid"
        mock_oauth_settings.notion_oauth_client_secret = "csecret"

        mock_http = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_refresh_response
        mock_http.post = AsyncMock(return_value=mock_resp)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_http

        response = await client.post(
            f"/api/v1/projects/{project_id}/publish/notion",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200

    result = await db_session.execute(
        select(NotionConfig).where(NotionConfig.user_id == user_id)
    )
    config = result.scalar_one()
    assert config.access_token == "ntn_refreshed_access"


# ─── Public export to reader's Notion ───


@pytest.mark.asyncio
async def test_export_public_note_creates_single_page(client, db_session):
    token = await _register_and_login(client, "notion-export-public@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    await _create_notion_config(db_session, user_id, connected=True)
    project_id = await _create_project(client, token, "Nota Pública Export")
    await _setup_compendium(client, token, project_id, db_session)

    # Publish to make it public
    pub = await client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pub.status_code == 200
    slug = pub.json()["slug"]

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.create_page = AsyncMock(return_value="exported-page-1")
        mock_wrapper.search = AsyncMock(return_value=[])

        response = await client.post(
            f"/api/v1/public/compendiums/{slug}/export/notion",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == slug
    assert data["notion_page_id"] == "exported-page-1"
    assert "notion.so" in data["notion_url"]
    mock_wrapper.create_page.assert_awaited_once()
    call_kwargs = mock_wrapper.create_page.await_args
    assert call_kwargs.kwargs["parent_page_id"] == "parent-page-123"
    assert call_kwargs.kwargs["title"] == "Nota Pública Export"


@pytest.mark.asyncio
async def test_export_public_note_requires_auth(client, db_session):
    response = await client.post(
        "/api/v1/public/compendiums/some-slug/export/notion",
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_export_public_note_requires_notion(client, db_session):
    token = await _register_and_login(client, "notion-export-nocon@test.com")
    project_id = await _create_project(client, token, "Sin Notion")
    await _setup_compendium(client, token, project_id, db_session)
    pub = await client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    slug = pub.json()["slug"]

    response = await client.post(
        f"/api/v1/public/compendiums/{slug}/export/notion",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_export_public_uses_search_fallback_for_parent(client, db_session):
    token = await _register_and_login(client, "notion-export-search@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    config = await _create_notion_config(db_session, user_id, connected=True)
    config.default_parent_page_id = None
    await db_session.commit()

    project_id = await _create_project(client, token, "Search Parent")
    await _setup_compendium(client, token, project_id, db_session)
    pub = await client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    slug = pub.json()["slug"]

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.search = AsyncMock(
            return_value=[{"id": "found-parent", "title": "Home", "object": "page"}]
        )
        mock_wrapper.create_page = AsyncMock(return_value="page-from-search")

        response = await client.post(
            f"/api/v1/public/compendiums/{slug}/export/notion",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert mock_wrapper.create_page.await_args.kwargs["parent_page_id"] == "found-parent"


@pytest.mark.asyncio
async def test_oauth_start_accepts_return_to(client, db_session):
    token = await _register_and_login(client, "notion-return-to@test.com")
    mock_settings = _make_mock_settings()

    with patch("app.modules.notion.oauth_state.settings", mock_settings), \
         patch("app.modules.notion.oauth_service.settings", mock_settings):
        response = await client.get(
            "/api/v1/notion/oauth/start?return_to=/compendiums/mi-nota",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "authorize_url" in data
    assert "state=" in data["authorize_url"]


# ─── Token expiry persistence ───


class _FakeAPIError(Exception):
    """Stand-in for notion_client.errors.APIResponseError for testing."""

    def __init__(self, status: int = 401, code: str = "unauthorized", message: str = ""):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@pytest.mark.asyncio
async def test_save_oauth_result_persists_expires_in(client, db_session):
    token = await _register_and_login(client, "notion-expires-in@test.com")
    from app.modules.auth.service import decode_access_token
    from app.modules.notion.oauth_service import save_oauth_result, NotionTokenResponse

    user_id = decode_access_token(token)
    from app.models.user import User

    user = (await db_session.execute(select(User).where(User.id == user_id))).scalar_one()

    token_data = NotionTokenResponse(
        access_token="ntn_access_with_expiry",
        refresh_token="ntn_refresh_with_expiry",
        token_type="bearer",
        workspace_id="ws-exp",
        workspace_name="Expiry Test",
        workspace_icon=None,
        bot_id="bot-exp",
        owner={"user_id": "nu-1", "email": "exp@test.com"},
        duplicated_template_id=None,
        expires_in=86400,
    )

    config = await save_oauth_result(db_session, user, token_data)

    assert config.token_expires_at is not None
    assert config.token_expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_save_oauth_result_no_expires_in_keeps_none(client, db_session):
    token = await _register_and_login(client, "notion-no-expires-in@test.com")
    from app.modules.auth.service import decode_access_token
    from app.modules.notion.oauth_service import save_oauth_result, NotionTokenResponse

    user_id = decode_access_token(token)
    from app.models.user import User

    user = (await db_session.execute(select(User).where(User.id == user_id))).scalar_one()

    token_data = NotionTokenResponse(
        access_token="ntn_access_no_expiry",
        refresh_token="ntn_refresh_no_expiry",
        token_type="bearer",
        workspace_id="ws-noexp",
        workspace_name="No Expiry Test",
        workspace_icon=None,
        bot_id="bot-noexp",
        owner={"user_id": "nu-2", "email": "noexp@test.com"},
        duplicated_template_id=None,
        expires_in=None,
    )

    config = await save_oauth_result(db_session, user, token_data)

    assert config.token_expires_at is None


@pytest.mark.asyncio
async def test_try_refresh_token_persists_expires_at(client, db_session):
    token = await _register_and_login(client, "notion-refresh-exp@test.com")
    from app.modules.auth.service import decode_access_token
    from app.modules.notion.oauth_service import try_refresh_token, NotionTokenResponse

    user_id = decode_access_token(token)
    config = await _create_notion_config(
        db_session, user_id, connected=True, with_refresh=True, expired=True
    )
    old_expires = config.token_expires_at

    mock_token_data = NotionTokenResponse(
        access_token="ntn_refreshed_access_v2",
        refresh_token="ntn_new_refresh_v2",
        token_type="bearer",
        workspace_id="ws-001",
        workspace_name="Test Workspace",
        workspace_icon=None,
        bot_id="bot-001",
        owner={"user_id": "notion-user-001", "email": "dr@test.com"},
        duplicated_template_id=None,
        expires_in=86400,
    )

    with patch(
        "app.modules.notion.oauth_service.refresh_access_token",
        new_callable=AsyncMock,
        return_value=mock_token_data,
    ):
        result = await try_refresh_token(db_session, config)

    assert result is True
    assert config.access_token == "ntn_refreshed_access_v2"
    assert config.token_expires_at is not None
    assert config.token_expires_at > datetime.now(timezone.utc)
    assert config.token_expires_at != old_expires


@pytest.mark.asyncio
async def test_try_refresh_token_keeps_old_expires_when_no_new(client, db_session):
    token = await _register_and_login(client, "notion-refresh-keep@test.com")
    from app.modules.auth.service import decode_access_token
    from app.modules.notion.oauth_service import try_refresh_token, NotionTokenResponse

    user_id = decode_access_token(token)
    config = await _create_notion_config(
        db_session, user_id, connected=True, with_refresh=True, expired=True
    )
    original_expires = config.token_expires_at

    mock_token_data = NotionTokenResponse(
        access_token="ntn_refreshed_no_expiry",
        refresh_token=None,
        token_type="bearer",
        workspace_id="ws-001",
        workspace_name="Test Workspace",
        workspace_icon=None,
        bot_id="bot-001",
        owner={"user_id": "notion-user-001", "email": "dr@test.com"},
        duplicated_template_id=None,
        expires_in=None,
    )

    with patch(
        "app.modules.notion.oauth_service.refresh_access_token",
        new_callable=AsyncMock,
        return_value=mock_token_data,
    ):
        result = await try_refresh_token(db_session, config)

    assert result is True
    assert config.token_expires_at == original_expires


# ─── 401 from Notion → 409 clean error ───


@pytest.mark.asyncio
async def test_export_returns_409_on_notion_401(client, db_session):
    token = await _register_and_login(client, "notion-401-export@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    await _create_notion_config(db_session, user_id, connected=True)
    project_id = await _create_project(client, token, "Notion 401 Test")
    await _setup_compendium(client, token, project_id, db_session)

    pub = await client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    slug = pub.json()["slug"]

    mock_error = _FakeAPIError(status=401, code="unauthorized", message="API token is invalid.")

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls, patch(
        "app.modules.notion.service.APIResponseError", _FakeAPIError
    ):
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.create_page = AsyncMock(side_effect=mock_error)

        response = await client.post(
            f"/api/v1/public/compendiums/{slug}/export/notion",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 409
    assert "expirado" in response.json()["detail"].lower() or "reconecta" in response.json()["detail"].lower()

    result = await db_session.execute(
        select(NotionConfig).where(NotionConfig.user_id == user_id)
    )
    config = result.scalar_one()
    assert config.is_connected is False


@pytest.mark.asyncio
async def test_publish_returns_409_on_notion_401(client, db_session):
    token = await _register_and_login(client, "notion-401-publish@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    await _create_notion_config(db_session, user_id, connected=True)
    project_id = await _create_project(client, token, "Publish 401 Test")
    await _setup_compendium(client, token, project_id, db_session)

    mock_error = _FakeAPIError(status=401, code="unauthorized", message="API token is invalid.")

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls, patch(
        "app.modules.notion.service.APIResponseError", _FakeAPIError
    ):
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.create_page = AsyncMock(side_effect=mock_error)

        response = await client.post(
            f"/api/v1/projects/{project_id}/publish/notion",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_search_returns_409_on_notion_401(client, db_session):
    token = await _register_and_login(client, "notion-401-search@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    await _create_notion_config(db_session, user_id, connected=True)

    mock_error = _FakeAPIError(status=401, code="unauthorized", message="API token is invalid.")

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls, patch(
        "app.modules.notion.service.APIResponseError", _FakeAPIError
    ):
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.search = AsyncMock(side_effect=mock_error)

        response = await client.get(
            "/api/v1/notion/search?query=test",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 409


# ─── Proactive refresh when token_expires_at is None ───


@pytest.mark.asyncio
async def test_ensure_fresh_token_refreshes_when_no_expires_and_stale(client, db_session):
    token = await _register_and_login(client, "notion-stale-refresh@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    config = await _create_notion_config(
        db_session, user_id, connected=True, with_refresh=True
    )
    config.token_expires_at = None
    config.last_refreshed_at = datetime.now(timezone.utc) - timedelta(hours=13)
    await db_session.commit()

    mock_token_data = {
        "access_token": "ntn_proactive_refresh",
        "refresh_token": "ntn_new_rt",
        "token_type": "bearer",
        "workspace_id": "ws-001",
        "workspace_name": "Test Workspace",
        "workspace_icon": None,
        "bot_id": "bot-001",
        "owner": {
            "type": "user",
            "user": {
                "id": "notion-uid",
                "object": "user",
                "name": "Dr. Test",
                "avatar_url": None,
                "type": "person",
                "person": {"email": "dr@test.com"},
            },
        },
        "duplicated_template_id": None,
        "expires_in": 86400,
    }

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls, \
        patch(
            "app.modules.notion.oauth_service.settings"
        ) as mock_oauth_settings, \
        patch(
            "app.modules.notion.oauth_service.httpx.AsyncClient"
        ) as mock_client_cls:
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.search = AsyncMock(
            return_value=[{"id": "page-1", "title": "Home", "object": "page"}]
        )

        mock_oauth_settings.notion_oauth_client_id = "cid"
        mock_oauth_settings.notion_oauth_client_secret = "csecret"

        mock_http = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_token_data
        mock_http.post = AsyncMock(return_value=mock_resp)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_http

        response = await client.get(
            "/api/v1/notion/search?query=test",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200

    result = await db_session.execute(
        select(NotionConfig).where(NotionConfig.user_id == user_id)
    )
    updated_config = result.scalar_one()
    assert updated_config.access_token == "ntn_proactive_refresh"
    assert updated_config.token_expires_at is not None


@pytest.mark.asyncio
async def test_ensure_fresh_token_skips_refresh_when_fresh(client, db_session):
    token = await _register_and_login(client, "notion-fresh-skip@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    config = await _create_notion_config(
        db_session, user_id, connected=True, with_refresh=True
    )
    config.token_expires_at = None
    config.last_refreshed_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.commit()

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.search = AsyncMock(
            return_value=[{"id": "page-1", "title": "Home", "object": "page"}]
        )

        response = await client.get(
            "/api/v1/notion/search?query=test",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200


# ─── Markdown table → Notion blocks ───


def test_md_to_notion_blocks_table_width_and_cells():
    from app.modules.notion.client import NotionClientWrapper

    md = (
        "| Columna A | Columna B | Columna C |\n"
        "| --- | --- | --- |\n"
        "| 1 | 2 | 3 |\n"
        "| **bold** | _italic_ | plain |\n"
    )
    blocks = NotionClientWrapper("dummy")._md_to_notion_blocks(md)

    table = [b for b in blocks if b["type"] == "table"]
    assert len(table) == 1
    table_block = table[0]["table"]
    assert table_block["table_width"] == 3
    assert table_block["has_column_header"] is True
    rows = table_block["children"]
    assert len(rows) == 3  # header + 2 body
    for row in rows:
        assert row["type"] == "table_row"
        cells = row["table_row"]["cells"]
        assert len(cells) == 3  # una celda por columna
        for cell in cells:
            assert isinstance(cell, list)
            assert all(isinstance(seg, dict) and "text" in seg for seg in cell)


# ─── Notion error mapping (≠ 401) ───


@pytest.mark.asyncio
async def test_export_returns_422_on_notion_400(client, db_session):
    token = await _register_and_login(client, "notion-400-export@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    await _create_notion_config(db_session, user_id, connected=True)
    project_id = await _create_project(client, token, "Notion 400 Test")
    await _setup_compendium(client, token, project_id, db_session)

    pub = await client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    slug = pub.json()["slug"]

    mock_error = _FakeAPIError(
        status=400,
        code="validation_error",
        message="Number of cells in table row must match the table width of the parent table",
    )

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls, patch(
        "app.modules.notion.service.APIResponseError", _FakeAPIError
    ):
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.create_page = AsyncMock(side_effect=mock_error)

        response = await client.post(
            f"/api/v1/public/compendiums/{slug}/export/notion",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422
    assert "Number of cells" in response.json()["detail"]


@pytest.mark.asyncio
async def test_export_returns_404_on_notion_404(client, db_session):
    token = await _register_and_login(client, "notion-404-export@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    await _create_notion_config(db_session, user_id, connected=True)
    project_id = await _create_project(client, token, "Notion 404 Test")
    await _setup_compendium(client, token, project_id, db_session)

    pub = await client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    slug = pub.json()["slug"]

    mock_error = _FakeAPIError(
        status=404,
        code="object_not_found",
        message="Could not find page with ID: parent-page-123",
    )

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls, patch(
        "app.modules.notion.service.APIResponseError", _FakeAPIError
    ):
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.create_page = AsyncMock(side_effect=mock_error)

        response = await client.post(
            f"/api/v1/public/compendiums/{slug}/export/notion",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert "no existe" in response.json()["detail"].lower() or \
        "compartido" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_publish_returns_422_on_notion_400(client, db_session):
    token = await _register_and_login(client, "notion-400-publish@test.com")
    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    await _create_notion_config(db_session, user_id, connected=True)
    project_id = await _create_project(client, token, "Publish 400 Test")
    await _setup_compendium(client, token, project_id, db_session)

    mock_error = _FakeAPIError(
        status=400,
        code="validation_error",
        message="body failed validation",
    )

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls, patch(
        "app.modules.notion.service.APIResponseError", _FakeAPIError
    ):
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.create_page = AsyncMock(side_effect=mock_error)

        response = await client.post(
            f"/api/v1/projects/{project_id}/publish/notion",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422
