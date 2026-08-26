from httpx import AsyncClient

from identity.api.router import REFRESH_COOKIE_NAME


async def _register(client: AsyncClient, owner_contact: str = "owner@example.com") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "business_name": "Test Business",
            "owner_name": "Jane Owner",
            "owner_contact": owner_contact,
            "password": "correct-horse-battery-staple",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_register_then_me(client: AsyncClient) -> None:
    tokens = await _register(client)
    assert REFRESH_COOKIE_NAME in client.cookies

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["staff_user"]["email_or_phone"] == "owner@example.com"
    assert body["merchant"]["business_name"] == "Test Business"


async def test_register_duplicate_contact_rejected(client: AsyncClient) -> None:
    await _register(client)

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "business_name": "Another Business",
            "owner_name": "John Owner",
            "owner_contact": "owner@example.com",
            "password": "another-password",
        },
    )

    assert response.status_code == 409


async def test_login_with_correct_password(client: AsyncClient) -> None:
    await _register(client)
    client.cookies.clear()

    response = await client.post(
        "/api/v1/auth/login",
        json={"email_or_phone": "owner@example.com", "password": "correct-horse-battery-staple"},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert REFRESH_COOKIE_NAME in client.cookies


async def test_login_with_wrong_password_rejected(client: AsyncClient) -> None:
    await _register(client)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email_or_phone": "owner@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


async def test_me_without_token_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


async def test_refresh_issues_new_access_token(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    new_access_token = response.json()["access_token"]
    assert new_access_token != tokens["access_token"]

    me_response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access_token}"}
    )
    assert me_response.status_code == 200


async def test_refresh_without_cookie_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401


async def test_refresh_cookie_is_lax_and_insecure_in_development(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "business_name": "Test Business",
            "owner_name": "Jane Owner",
            "owner_contact": "cookie-dev@example.com",
            "password": "correct-horse-battery-staple",
        },
    )

    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "samesite=lax" in set_cookie
    assert "secure" not in set_cookie


async def test_refresh_cookie_is_samesite_none_and_secure_in_production(
    client: AsyncClient, monkeypatch
) -> None:
    from shared.config import get_settings

    monkeypatch.setattr(get_settings(), "env", "production")

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "business_name": "Test Business",
            "owner_name": "Jane Owner",
            "owner_contact": "cookie-prod@example.com",
            "password": "correct-horse-battery-staple",
        },
    )

    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "samesite=none" in set_cookie
    assert "secure" in set_cookie


async def test_logout_clears_refresh_cookie(client: AsyncClient) -> None:
    await _register(client)
    assert REFRESH_COOKIE_NAME in client.cookies

    logout_response = await client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 204

    refresh_response = await client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 401


async def test_me_scoped_to_own_merchant(client: AsyncClient) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    tokens_b = await _register(client, owner_contact="owner-b@example.com")

    me_a = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens_a['access_token']}"}
    )
    me_b = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens_b['access_token']}"}
    )

    assert me_a.json()["merchant"]["merchant_id"] != me_b.json()["merchant"]["merchant_id"]
