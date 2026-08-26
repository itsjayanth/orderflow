from httpx import AsyncClient


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


def _auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_get_whatsapp_settings_defaults_to_pending(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.get("/api/v1/onboarding/whatsapp", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert body["connection_status"] == "pending"
    assert body["phone_number_id"] is None
    assert body["access_token_set"] is False


async def test_update_whatsapp_settings_marks_connected(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.put(
        "/api/v1/onboarding/whatsapp",
        json={
            "phone_number_id": "1234567890",
            "access_token": "dummy-meta-access-token",
            "display_phone_number": "+91 90000 00000",
        },
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["connection_status"] == "connected"
    assert body["phone_number_id"] == "1234567890"
    assert body["display_phone_number"] == "+91 90000 00000"
    assert body["access_token_set"] is True
    # The raw token is never echoed back.
    assert "dummy-meta-access-token" not in response.text


async def test_whatsapp_settings_persist_and_are_readable_after_update(
    client: AsyncClient,
) -> None:
    tokens = await _register(client)
    await client.put(
        "/api/v1/onboarding/whatsapp",
        json={"phone_number_id": "1234567890", "access_token": "dummy-meta-access-token"},
        headers=_auth_headers(tokens),
    )

    response = await client.get("/api/v1/onboarding/whatsapp", headers=_auth_headers(tokens))

    assert response.status_code == 200
    assert response.json()["phone_number_id"] == "1234567890"


async def test_whatsapp_settings_isolated_between_merchants(client: AsyncClient) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    await client.put(
        "/api/v1/onboarding/whatsapp",
        json={"phone_number_id": "1111111111", "access_token": "token-a"},
        headers=_auth_headers(tokens_a),
    )
    tokens_b = await _register(client, owner_contact="owner-b@example.com")

    response = await client.get("/api/v1/onboarding/whatsapp", headers=_auth_headers(tokens_b))

    assert response.status_code == 200
    body = response.json()
    assert body["phone_number_id"] is None
    assert body["connection_status"] == "pending"
