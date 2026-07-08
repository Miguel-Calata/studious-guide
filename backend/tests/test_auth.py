import pytest


@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@test.com",
            "password": "Test1234",
            "full_name": "New User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@test.com"
    assert data["role"] == "creator"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {"email": "dup@test.com", "password": "Test1234"}
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201

    r2 = await client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login@test.com", "password": "Test1234"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@test.com", "password": "Test1234"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nope@test.com", "password": "WrongPass1"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "me@test.com", "password": "Test1234"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "me@test.com", "password": "Test1234"},
    )
    token = login.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@test.com"


@pytest.mark.asyncio
async def test_refresh_token(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "refresh@test.com", "password": "Test1234"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@test.com", "password": "Test1234"},
    )
    refresh_token = login.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_with_invalid_token(client):
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not-a-valid-token"},
    )
    assert response.status_code == 401
