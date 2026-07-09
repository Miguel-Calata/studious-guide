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


@pytest.mark.asyncio
async def test_create_project(client):
    token = await _register_and_login(client, "proj-create@test.com")
    response = await client.post(
        "/api/v1/projects",
        json={"name": "Lesión Renal Aguda", "description": "Test project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Lesión Renal Aguda"
    assert data["slug"].startswith("lesion-renal-aguda")
    assert data["status"] == ProjectStatus.DRAFT


@pytest.mark.asyncio
async def test_create_project_without_description(client):
    token = await _register_and_login(client, "proj-no-desc@test.com")
    response = await client.post(
        "/api/v1/projects",
        json={"name": "Proyecto sin descripción"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["description"] is None


@pytest.mark.asyncio
async def test_list_projects_excludes_archived(client):
    token = await _register_and_login(client, "proj-list@test.com")
    await client.post(
        "/api/v1/projects",
        json={"name": "Active Project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    create_archived = await client.post(
        "/api/v1/projects",
        json={"name": "Archived Project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    archived_id = create_archived.json()["id"]
    await client.delete(
        f"/api/v1/projects/{archived_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Active Project"


@pytest.mark.asyncio
async def test_update_project(client):
    token = await _register_and_login(client, "proj-update@test.com")
    created = await client.post(
        "/api/v1/projects",
        json={"name": "Original Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = created.json()["id"]

    response = await client.put(
        f"/api/v1/projects/{project_id}",
        json={"name": "Updated Name", "description": "Updated description"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "Updated description"


@pytest.mark.asyncio
async def test_archive_project(client):
    token = await _register_and_login(client, "proj-archive@test.com")
    created = await client.post(
        "/api/v1/projects",
        json={"name": "To Archive"},
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = created.json()["id"]

    response = await client.delete(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204

    get_response = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Archived projects are still accessible by ID but excluded from list
    assert get_response.status_code == 200
    assert get_response.json()["status"] == ProjectStatus.ARCHIVED


@pytest.mark.asyncio
async def test_cannot_access_other_user_project(client):
    token_a = await _register_and_login(client, "proj-owner@test.com")
    token_b = await _register_and_login(client, "proj-intruder@test.com")

    created = await client.post(
        "/api/v1/projects",
        json={"name": "Private Project"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    project_id = created.json()["id"]

    response = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 404
