import io

import pytest


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


def _pdf_file(name: str = "test.pdf", content: bytes = b"%PDF-1.4 test"):
    return (
        name,
        io.BytesIO(content),
        "application/pdf",
    )


@pytest.mark.asyncio
async def test_upload_single_pdf(client):
    token = await _register_and_login(client, "doc-upload@test.com")
    project_id = await _create_project(client, token)

    response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"files": _pdf_file()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["documents"]) == 1
    assert data["documents"][0]["filename"] == "test.pdf"
    assert data["documents"][0]["document_type"] == "article"


@pytest.mark.asyncio
async def test_upload_pdf_with_document_type(client):
    token = await _register_and_login(client, "doc-type@test.com")
    project_id = await _create_project(client, token)

    response = await client.post(
        f"/api/v1/projects/{project_id}/documents?document_type=guideline",
        files={"files": _pdf_file()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["documents"][0]["document_type"] == "guideline"


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf(client):
    token = await _register_and_login(client, "doc-reject@test.com")
    project_id = await _create_project(client, token)

    response = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"files": ("not-a-pdf.txt", io.BytesIO(b"hello"), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_and_get_documents(client):
    token = await _register_and_login(client, "doc-list@test.com")
    project_id = await _create_project(client, token)

    upload = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"files": _pdf_file()},
        headers={"Authorization": f"Bearer {token}"},
    )
    document_id = upload.json()["documents"][0]["id"]

    list_response = await client.get(
        f"/api/v1/projects/{project_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = await client.get(
        f"/api/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200
    assert get_response.json()["id"] == document_id


@pytest.mark.asyncio
async def test_download_and_delete_document(client):
    token = await _register_and_login(client, "doc-download@test.com")
    project_id = await _create_project(client, token)

    upload = await client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"files": _pdf_file(content=b"%PDF-1.4 custom content")},
        headers={"Authorization": f"Bearer {token}"},
    )
    document_id = upload.json()["documents"][0]["id"]

    download = await client.get(
        f"/api/v1/documents/{document_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert download.status_code == 200
    assert download.content == b"%PDF-1.4 custom content"

    delete = await client.delete(
        f"/api/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete.status_code == 204

    get_response = await client.get(
        f"/api/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 404
