import io
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, update

from app.models.compendium_section import CompendiumSection, SectionStatus
from app.models.extraction import Extraction, ExtractionStatus
from app.models.notion_config import NotionConfig
from app.models.project import Project, ProjectStatus
from app.models.source_document import SourceDocument


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


async def _create_notion_config(db_session, user_id: str, connected: bool = True):
    config = NotionConfig(
        user_id=user_id,
        api_key="ntn_test_key_12345",
        workspace_name="Test Workspace",
        default_parent_page_id="parent-page-123",
        is_connected=connected,
    )
    db_session.add(config)
    await db_session.commit()
    await db_session.refresh(config)
    return config


@pytest.mark.asyncio
async def test_connect_valid_key(client, db_session):
    token = await _register_and_login(client, "notion-connect@test.com")

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.validate_key = AsyncMock(return_value="Mi Workspace")

        response = await client.post(
            "/api/v1/notion/connect",
            json={"api_key": "ntn_valid_key"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["is_connected"] is True
    assert data["workspace_name"] == "Mi Workspace"

    from app.modules.auth.service import decode_access_token

    user_id = decode_access_token(token)
    result = await db_session.execute(
        select(NotionConfig).where(NotionConfig.user_id == user_id)
    )
    # Verify it was saved encrypted (raw DB value != plaintext)
    configs = list(result.scalars().all())
    assert len(configs) == 1
    assert configs[0].api_key_encrypted != "ntn_valid_key"
    assert configs[0].api_key == "ntn_valid_key"  # decryption works


@pytest.mark.asyncio
async def test_connect_invalid_key(client, db_session):
    token = await _register_and_login(client, "notion-invalid@test.com")

    with patch(
        "app.modules.notion.service.NotionClientWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.validate_key = AsyncMock(
            side_effect=Exception("Unauthorized")
        )

        response = await client.post(
            "/api/v1/notion/connect",
            json={"api_key": "bad_key"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401


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


@pytest.mark.asyncio
async def test_status_disconnected(client, db_session):
    token = await _register_and_login(client, "notion-status-disc@test.com")
    # No config exists
    response = await client.get(
        "/api/v1/notion/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_connected"] is False


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

    # Verify notion_page_id was saved on sections
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

    # Pre-set notion_page_id on sections to simulate prior publish
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
    # Root page created once (new)
    assert len(create_called) == 1
    # 11 sections updated (not created)
    assert len(update_called) == 11
    assert all(p.startswith("existing-page-") for p in update_called)


@pytest.mark.asyncio
async def test_publish_fails_without_connection(client, db_session):
    token = await _register_and_login(client, "notion-noconn@test.com")
    # No config
    project_id = await _create_project(client, token)
    await _setup_compendium(client, token, project_id, db_session)

    response = await client.post(
        f"/api/v1/projects/{project_id}/publish/notion",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
