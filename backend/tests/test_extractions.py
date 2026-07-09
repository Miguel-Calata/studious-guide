import io

import pytest

from app.models.project import ProjectStatus


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


async def _create_project(client, token: str, name: str = "Test Project"):
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


@pytest.mark.asyncio
async def test_create_extraction_returns_201_pending(client):
    token = await _register_and_login(client, "ext-create@test.com")
    project_id = await _create_project(client, token)
    document_id = await _upload_document(client, token, project_id)

    response = await client.post(
        f"/api/v1/documents/{document_id}/extract",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["content"] == ""
    assert data["source_document_id"] == document_id


@pytest.mark.asyncio
async def test_cannot_create_duplicate_extraction(client):
    token = await _register_and_login(client, "ext-dup@test.com")
    project_id = await _create_project(client, token)
    document_id = await _upload_document(client, token, project_id)

    await client.post(
        f"/api/v1/documents/{document_id}/extract",
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.post(
        f"/api/v1/documents/{document_id}/extract",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_retry_only_on_failed(client):
    token = await _register_and_login(client, "ext-retry@test.com")
    project_id = await _create_project(client, token)
    document_id = await _upload_document(client, token, project_id)

    create_resp = await client.post(
        f"/api/v1/documents/{document_id}/extract",
        headers={"Authorization": f"Bearer {token}"},
    )
    extraction_id = create_resp.json()["id"]

    response = await client.post(
        f"/api/v1/extractions/{extraction_id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_project_transitions_to_extracting(client):
    token = await _register_and_login(client, "ext-status@test.com")
    project_id = await _create_project(client, token)
    document_id = await _upload_document(client, token, project_id)

    await client.post(
        f"/api/v1/documents/{document_id}/extract",
        headers={"Authorization": f"Bearer {token}"},
    )

    project_resp = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert project_resp.json()["status"] == ProjectStatus.EXTRACTING


@pytest.mark.asyncio
async def test_get_extraction(client):
    token = await _register_and_login(client, "ext-get@test.com")
    project_id = await _create_project(client, token)
    document_id = await _upload_document(client, token, project_id)

    create_resp = await client.post(
        f"/api/v1/documents/{document_id}/extract",
        headers={"Authorization": f"Bearer {token}"},
    )
    extraction_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/v1/extractions/{extraction_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == extraction_id


@pytest.mark.asyncio
async def test_get_extraction_status(client):
    token = await _register_and_login(client, "ext-status-get@test.com")
    project_id = await _create_project(client, token)
    document_id = await _upload_document(client, token, project_id)

    create_resp = await client.post(
        f"/api/v1/documents/{document_id}/extract",
        headers={"Authorization": f"Bearer {token}"},
    )
    extraction_id = create_resp.json()["id"]

    response = await client.get(
        f"/api/v1/extractions/{extraction_id}/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == extraction_id
    assert data["status"] == "pending"
    assert data["error_message"] is None


@pytest.mark.asyncio
async def test_extract_all_creates_extractions(client):
    token = await _register_and_login(client, "ext-all@test.com")
    project_id = await _create_project(client, token, "ExtractAll Project")
    doc1 = await _upload_document(client, token, project_id)
    doc2 = await _upload_document(client, token, project_id)

    response = await client.post(
        f"/api/v1/projects/{project_id}/extract-all",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_documents"] == 2
    assert data["enqueued"] == 2
    assert data["skipped"] == 0
    assert data["project_status"] == ProjectStatus.EXTRACTING


@pytest.mark.asyncio
async def test_extract_all_skips_already_extracted(client):
    token = await _register_and_login(client, "ext-all-skip@test.com")
    project_id = await _create_project(client, token, "Skip Project")
    doc1 = await _upload_document(client, token, project_id)
    doc2 = await _upload_document(client, token, project_id)

    await client.post(
        f"/api/v1/documents/{doc1}/extract",
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.post(
        f"/api/v1/projects/{project_id}/extract-all",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_documents"] == 2
    assert data["enqueued"] == 1
    assert data["skipped"] == 1


@pytest.mark.asyncio
async def test_extract_all_transitions_project(client):
    token = await _register_and_login(client, "ext-all-trans@test.com")
    project_id = await _create_project(client, token, "Trans Project")
    await _upload_document(client, token, project_id)

    await client.post(
        f"/api/v1/projects/{project_id}/extract-all",
        headers={"Authorization": f"Bearer {token}"},
    )

    project_resp = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert project_resp.json()["status"] == ProjectStatus.EXTRACTING


@pytest.mark.asyncio
async def test_extract_all_no_documents(client):
    token = await _register_and_login(client, "ext-all-empty@test.com")
    project_id = await _create_project(client, token, "Empty Project")

    response = await client.post(
        f"/api/v1/projects/{project_id}/extract-all",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_documents"] == 0
    assert data["enqueued"] == 0
    assert data["skipped"] == 0
    assert data["project_status"] == ProjectStatus.DRAFT
