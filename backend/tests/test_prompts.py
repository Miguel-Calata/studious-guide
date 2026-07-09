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


@pytest.mark.asyncio
async def test_seed_prompts_are_loaded(client):
    token = await _register_and_login(client, "prompt-seed@test.com")

    response = await client.get(
        "/api/v1/prompts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    prompts = response.json()
    assert len(prompts) == 6

    names = {p["name"] for p in prompts}
    expected = {
        "system_prompt_sam_v9",
        "extraction_v3_bmj",
        "extraction_v5_guideline",
        "extraction_articles",
        "audit",
        "patch_gemini_density",
    }
    assert names == expected


@pytest.mark.asyncio
async def test_get_prompt_by_name(client):
    token = await _register_and_login(client, "prompt-get@test.com")

    response = await client.get(
        "/api/v1/prompts/system_prompt_sam_v9",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "system_prompt_sam_v9"
    assert data["type"] == "system"
    assert data["version"] == 1
    assert data["is_active"] is True
    assert len(data["content"]) > 100


@pytest.mark.asyncio
async def test_get_nonexistent_prompt_returns_404(client):
    token = await _register_and_login(client, "prompt-404@test.com")

    response = await client.get(
        "/api/v1/prompts/nonexistent_prompt",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
