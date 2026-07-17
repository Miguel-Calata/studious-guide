import io

import pytest
from sqlalchemy import select, update

from app.models.compendium_section import CompendiumSection, SectionStatus
from app.models.extraction import Extraction, ExtractionStatus
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


async def _create_project(client, token: str, name: str = "Sources Project"):
    response = await client.post(
        "/api/v1/projects",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()["id"]


async def _upload_document(client, token: str, project_id: str):
    response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        data={"document_type": "article"},
        files={"files": ("test.pdf", io.BytesIO(b"%PDF-1.4 test content"), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.json()["documents"][0]


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
    ext = await _create_extraction(client, token, doc["id"])
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
    return doc


@pytest.mark.asyncio
async def test_sources_returns_401_for_anonymous(client, db_session):
    response = await client.get("/public/compendiums/any-slug/sources")
    assert response.status_code == 401
    response = await client.get(
        "/public/compendiums/any-slug/sources/any-doc-id"
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sources_returns_404_for_nonexistent(client):
    token = await _register_and_login(client, "sources-404@test.com")
    response = await client.get(
        "/public/compendiums/nonexistent/sources",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    response = await client.get(
        "/public/compendiums/nonexistent/sources/any-doc-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sources_returns_403_for_unpublished_compendium(client, db_session):
    token = await _register_and_login(client, "sources-unpub@test.com")
    project_id = await _create_project(client, token, "Unpublished Project")
    doc = await _upload_document(client, token, project_id)
    response = await client.get(
        "/public/compendiums/unpublished-project/sources",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    response = await client.get(
        f"/public/compendiums/unpublished-project/sources/{doc['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sources_lists_documents_for_published(client, db_session):
    token = await _register_and_login(client, "sources-list@test.com")
    project_id = await _create_project(client, token, "List Sources")
    await _setup_compendium(client, token, project_id, db_session)
    publish_resp = await client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    slug = publish_resp.json()["slug"]

    response = await client.get(
        f"/public/compendiums/{slug}/sources",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["filename"] == "test.pdf"
    assert data[0]["document_type"] == "article"
    assert data[0]["file_size"] > 0
    assert "id" in data[0]
    assert "uploaded_at" in data[0]


@pytest.mark.asyncio
async def test_sources_download_streams_pdf_for_published(client, db_session, test_storage):
    token = await _register_and_login(client, "sources-dl@test.com")
    project_id = await _create_project(client, token, "Download Source")
    doc = await _setup_compendium(client, token, project_id, db_session)
    publish_resp = await client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    slug = publish_resp.json()["slug"]

    response = await client.get(
        f"/public/compendiums/{slug}/sources/{doc['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.headers.get("content-type") == "application/pdf"
    content_disp = response.headers.get("content-disposition", "")
    assert "inline" in content_disp
    assert "test.pdf" in content_disp
    assert b"%PDF-1.4 test content" in response.content


@pytest.mark.asyncio
async def test_sources_404_for_wrong_document_id(client, db_session):
    token = await _register_and_login(client, "sources-wrong@test.com")
    project_id = await _create_project(client, token, "Wrong Doc")
    await _setup_compendium(client, token, project_id, db_session)
    publish_resp = await client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    slug = publish_resp.json()["slug"]

    response = await client.get(
        f"/public/compendiums/{slug}/sources/nonexistent-doc-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sources_accessible_by_any_registered_user(client, db_session):
    owner_token = await _register_and_login(client, "sources-owner@test.com")
    project_id = await _create_project(client, owner_token, "Shared Sources")
    await _setup_compendium(client, owner_token, project_id, db_session)
    publish_resp = await client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    slug = publish_resp.json()["slug"]

    other_token = await _register_and_login(
        client, "sources-other@test.com", "OtherPass1"
    )
    response = await client.get(
        f"/public/compendiums/{slug}/sources",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
