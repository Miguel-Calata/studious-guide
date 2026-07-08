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


async def _create_project(client, token: str, name: str = "Publish Project"):
    response = await client.post(
        "/api/v1/projects/",
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
    """Helper: merge + generate + complete all sections."""
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


@pytest.mark.asyncio
async def test_publish_success(client, db_session):
    token = await _register_and_login(client, "pub-success@test.com")
    project_id = await _create_project(client, token, "Lesión Renal Aguda")
    await _setup_compendium(client, token, project_id, db_session)

    response = await client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    assert data["sections_included"] == 11
    assert data["project_status"] == ProjectStatus.COMPLETED
    assert data["public_url"] is not None
    assert data["slug"] is not None


@pytest.mark.asyncio
async def test_publish_without_all_sections_fails(client, db_session):
    token = await _register_and_login(client, "pub-incomplete@test.com")
    project_id = await _create_project(client, token)
    doc = await _upload_document(client, token, project_id)
    ext = await _create_extraction(client, token, doc)
    await _complete_extraction(db_session, ext, "Content")

    await client.post(
        f"/api/v1/projects/{project_id}/merge",
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/api/v1/projects/{project_id}/generate",
        headers={"Authorization": f"Bearer {token}"},
    )

    await db_session.execute(
        update(Project)
        .where(Project.id == project_id)
        .values(status=ProjectStatus.REVIEW)
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    assert "incompletas" in response.json()["detail"]


@pytest.mark.asyncio
async def test_publish_file_exists_in_storage(client, db_session, test_storage):
    token = await _register_and_login(client, "pub-storage@test.com")
    project_id = await _create_project(client, token, "Test Pathology")
    await _setup_compendium(client, token, project_id, db_session)

    response = await client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    slug = response.json()["slug"]
    exists = await test_storage.exists(f"compendiums/{slug}.md")
    assert exists


@pytest.mark.asyncio
async def test_public_list_returns_published(client, db_session):
    token = await _register_and_login(client, "pub-list@test.com")
    project_id = await _create_project(client, token, "Public LRA")
    await _setup_compendium(client, token, project_id, db_session)

    await client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get("/public/compendiums")
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1
    assert any("Public LRA" in item["name"] for item in items)


@pytest.mark.asyncio
async def test_public_download_returns_markdown(client, db_session):
    token = await _register_and_login(client, "pub-download@test.com")
    project_id = await _create_project(client, token, "Download Test")
    await _setup_compendium(client, token, project_id, db_session)

    publish_resp = await client.post(
        f"/api/v1/projects/{project_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    slug = publish_resp.json()["slug"]

    response = await client.get(f"/public/compendiums/{slug}/download")
    assert response.status_code == 200
    assert "text/markdown" in response.headers.get("content-type", "")
    body = response.text
    assert "# Download Test" in body
    assert "Content-Disposition" in response.headers


@pytest.mark.asyncio
async def test_public_endpoint_404_for_unpublished(client, db_session):
    response = await client.get("/public/compendiums/nonexistent-slug")
    assert response.status_code == 404

    response = await client.get("/public/compendiums/nonexistent-slug/download")
    assert response.status_code == 404

    response = await client.get("/public/compendiums/nonexistent-slug/sections/1")
    assert response.status_code == 404
