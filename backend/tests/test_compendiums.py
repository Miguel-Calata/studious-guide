import io

import pytest
from sqlalchemy import select, update

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


async def _create_project(client, token: str, name: str = "Compendium Project"):
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


async def _complete_extraction(db_session, extraction_id: str, content: str = "Extracted clinical content"):
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


@pytest.mark.asyncio
async def test_merge_produces_merged_content(client, db_session):
    token = await _register_and_login(client, "comp-merge@test.com")
    project_id = await _create_project(client, token)
    doc1 = await _upload_document(client, token, project_id)
    doc2 = await _upload_document(client, token, project_id)
    ext1 = await _create_extraction(client, token, doc1)
    ext2 = await _create_extraction(client, token, doc2)
    await _complete_extraction(db_session, ext1, "Content from doc 1")
    await _complete_extraction(db_session, ext2, "Content from doc 2")

    response = await client.post(
        f"/api/v1/projects/{project_id}/merge",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["merged_char_count"] > 0
    assert data["project_id"] == project_id


@pytest.mark.asyncio
async def test_merge_with_no_extractions_raises_error(client):
    token = await _register_and_login(client, "comp-merge-empty@test.com")
    project_id = await _create_project(client, token)

    response = await client.post(
        f"/api/v1/projects/{project_id}/merge",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_merge_cleans_continuation_markers(client, db_session):
    token = await _register_and_login(client, "comp-merge-clean@test.com")
    project_id = await _create_project(client, token)
    doc = await _upload_document(client, token, project_id)
    ext = await _create_extraction(client, token, doc)
    await _complete_extraction(
        db_session, ext,
        "Line 1\n\n[CONTINÚA — Pendiente desde: xxx]\n\nLine 2\n\nstrongHIDE ALL rest"
    )

    response = await client.post(
        f"/api/v1/projects/{project_id}/merge",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["merged_char_count"] > 0

    project_resp = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    merged = project_resp.json()["merged_content"]
    assert "CONTINÚA" not in merged
    assert "HIDE ALL" not in merged
    assert "Line 1" in merged
    assert "Line 2" in merged


@pytest.mark.asyncio
async def test_generate_creates_eleven_sections(client, db_session):
    token = await _register_and_login(client, "comp-gen@test.com")
    project_id = await _create_project(client, token)
    doc = await _upload_document(client, token, project_id)
    ext = await _create_extraction(client, token, doc)
    await _complete_extraction(db_session, ext, "Some content")

    await client.post(
        f"/api/v1/projects/{project_id}/merge",
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.post(
        f"/api/v1/projects/{project_id}/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sections_created"] == 11
    assert data["project_status"] == ProjectStatus.GENERATING


@pytest.mark.asyncio
async def test_generate_without_merged_content_fails(client, db_session):
    token = await _register_and_login(client, "comp-gen-nomerge@test.com")
    project_id = await _create_project(client, token)
    doc = await _upload_document(client, token, project_id)
    ext = await _create_extraction(client, token, doc)
    await _complete_extraction(db_session, ext, "Content")

    response = await client.post(
        f"/api/v1/projects/{project_id}/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_sections_returns_eleven(client, db_session):
    token = await _register_and_login(client, "comp-list@test.com")
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

    response = await client.get(
        f"/api/v1/projects/{project_id}/sections",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    sections = response.json()
    assert len(sections) == 11
    numbers = [s["section_number"] for s in sections]
    assert numbers == list(range(1, 12))


@pytest.mark.asyncio
async def test_get_specific_section(client, db_session):
    token = await _register_and_login(client, "comp-get@test.com")
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

    list_resp = await client.get(
        f"/api/v1/projects/{project_id}/sections",
        headers={"Authorization": f"Bearer {token}"},
    )
    section_id = list_resp.json()[0]["id"]

    response = await client.get(
        f"/api/v1/sections/{section_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["section_number"] == 1


@pytest.mark.asyncio
async def test_update_section_content(client, db_session):
    token = await _register_and_login(client, "comp-update@test.com")
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

    list_resp = await client.get(
        f"/api/v1/projects/{project_id}/sections",
        headers={"Authorization": f"Bearer {token}"},
    )
    section_id = list_resp.json()[0]["id"]

    response = await client.put(
        f"/api/v1/sections/{section_id}",
        json={"content": "Edited content by hand"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["content"] == "Edited content by hand"


@pytest.mark.asyncio
async def test_regenerate_resets_status(client, db_session):
    from app.models.compendium_section import CompendiumSection, SectionStatus

    token = await _register_and_login(client, "comp-regen@test.com")
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

    list_resp = await client.get(
        f"/api/v1/projects/{project_id}/sections",
        headers={"Authorization": f"Bearer {token}"},
    )
    section = list_resp.json()[0]
    section_id = section["id"]

    await db_session.execute(
        update(CompendiumSection)
        .where(CompendiumSection.id == section_id)
        .values(status=SectionStatus.COMPLETED, content="Generated content")
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/sections/{section_id}/regenerate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_draft_to_generating_is_valid_transition(client, db_session):
    token = await _register_and_login(client, "comp-transition@test.com")
    project_id = await _create_project(client, token)
    doc = await _upload_document(client, token, project_id)
    ext = await _create_extraction(client, token, doc)
    await _complete_extraction(db_session, ext, "Content")

    await client.post(
        f"/api/v1/projects/{project_id}/merge",
        headers={"Authorization": f"Bearer {token}"},
    )

    project_resp = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert project_resp.json()["status"] == ProjectStatus.DRAFT

    await client.post(
        f"/api/v1/projects/{project_id}/generate",
        headers={"Authorization": f"Bearer {token}"},
    )

    project_resp = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert project_resp.json()["status"] == ProjectStatus.GENERATING


@pytest.mark.asyncio
async def test_cannot_generate_twice(client, db_session):
    token = await _register_and_login(client, "comp-twice@test.com")
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

    response = await client.post(
        f"/api/v1/projects/{project_id}/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
