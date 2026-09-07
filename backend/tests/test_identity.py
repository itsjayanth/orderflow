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


# --- Refresh-token revocation -------------------------------------------


async def test_logout_revokes_refresh_token_server_side(client: AsyncClient) -> None:
    """Server-side revocation, not just the client-side cookie clear that
    test_logout_clears_refresh_cookie above exercises: even a client that
    kept holding the raw refresh token JWT (e.g. it leaked, or the cookie
    jar wasn't cleared) can no longer use it to mint a new access token
    after logout."""
    await _register(client)
    old_refresh_token = client.cookies[REFRESH_COOKIE_NAME]

    logout_response = await client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 204

    # Re-present the pre-logout refresh token directly, bypassing whatever
    # the logout response told the cookie jar to do.
    client.cookies.set(REFRESH_COOKIE_NAME, old_refresh_token)
    refresh_response = await client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 401


async def test_rotated_away_refresh_token_cannot_be_reused(client: AsyncClient) -> None:
    """Reuse detection: once a refresh token has been rotated (successfully
    exchanged for a new pair), presenting that same OLD token again must be
    rejected -- it's no longer the client's current token, so a second use
    of it is a signal of a stolen/replayed token, not a legitimate retry."""
    await _register(client)
    old_refresh_token = client.cookies[REFRESH_COOKIE_NAME]

    first_refresh = await client.post("/api/v1/auth/refresh")
    assert first_refresh.status_code == 200
    new_refresh_token = client.cookies[REFRESH_COOKIE_NAME]
    assert new_refresh_token != old_refresh_token

    # Replay the pre-rotation token.
    client.cookies.set(REFRESH_COOKIE_NAME, old_refresh_token)
    replay_response = await client.post("/api/v1/auth/refresh")
    assert replay_response.status_code == 401

    # The legitimate, rotated-to token must still work -- rotation isn't
    # itself treated as a compromise signal, only reuse of the old token is.
    client.cookies.set(REFRESH_COOKIE_NAME, new_refresh_token)
    second_refresh = await client.post("/api/v1/auth/refresh")
    assert second_refresh.status_code == 200


async def test_fresh_refresh_token_still_works(client: AsyncClient) -> None:
    """Regression guard: a refresh token that was never rotated or used for
    logout keeps working -- the denylist must not reject tokens it was
    never told to revoke."""
    tokens = await _register(client)

    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    new_access_token = response.json()["access_token"]
    assert new_access_token != tokens["access_token"]


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


# --- Appointment booking toggle ------------------------------------------


def _auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_me_reports_no_vertical_by_default(client: AsyncClient) -> None:
    """VERTICAL_TOGGLE_PLAN.md Phase T1: a freshly-registered merchant has
    neither vertical enabled yet until the onboarding wizard's first step
    (or, later, Settings) sets one -- see test_onboarding_flow.py's
    vertical-selection endpoint tests."""
    tokens = await _register(client)

    response = await client.get("/api/v1/auth/me", headers=_auth_headers(tokens))

    assert response.status_code == 200
    assert response.json()["merchant"]["restaurant_enabled"] is False
    assert response.json()["merchant"]["appointment_enabled"] is False


# --- Website link -----------------------------------------------------


async def test_website_link_round_trips_through_me(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.put(
        "/api/v1/auth/website-link",
        json={"website_url": "https://example.com"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    assert response.json()["website_url"] == "https://example.com"

    me_response = await client.get("/api/v1/auth/me", headers=_auth_headers(tokens))
    assert me_response.json()["merchant"]["website_url"] == "https://example.com"


async def test_website_link_blank_clears_it(client: AsyncClient) -> None:
    tokens = await _register(client)
    await client.put(
        "/api/v1/auth/website-link",
        json={"website_url": "https://example.com"},
        headers=_auth_headers(tokens),
    )

    response = await client.put(
        "/api/v1/auth/website-link",
        json={"website_url": "   "},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    assert response.json()["website_url"] is None

    me_response = await client.get("/api/v1/auth/me", headers=_auth_headers(tokens))
    assert me_response.json()["merchant"]["website_url"] is None


async def test_website_link_without_scheme_rejected(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.put(
        "/api/v1/auth/website-link",
        json={"website_url": "example.com"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 422


async def test_website_link_click_stats(client: AsyncClient, db_session) -> None:
    import uuid as uuid_module

    from identity.adapters.repository import WebsiteLinkClickRepository

    tokens = await _register(client)
    me_response = await client.get("/api/v1/auth/me", headers=_auth_headers(tokens))
    merchant_id = uuid_module.UUID(me_response.json()["merchant"]["merchant_id"])

    click_repo = WebsiteLinkClickRepository(db_session)
    await click_repo.record(merchant_id)
    await click_repo.record(merchant_id)
    await db_session.commit()

    response = await client.get(
        "/api/v1/auth/website-link/clicks", headers=_auth_headers(tokens)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["days"] == 7
