from httpx import AsyncClient

from onboarding.domain import embedded_signup as embedded_signup_domain
from shared.config import get_settings


async def _register(client: AsyncClient, owner_contact: str = "owner@example.com") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "business_name": "Test Kitchen",
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


async def test_update_whatsapp_settings_reports_manual_connection_method(
    client: AsyncClient,
) -> None:
    tokens = await _register(client)

    response = await client.put(
        "/api/v1/onboarding/whatsapp",
        json={"phone_number_id": "1234567890", "access_token": "dummy-meta-access-token"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    assert response.json()["connection_method"] == "manual"


async def test_embedded_signup_config_reports_not_configured_by_default(
    client: AsyncClient, monkeypatch
) -> None:
    get_settings.cache_clear()
    monkeypatch.delenv("META_APP_ID", raising=False)
    monkeypatch.delenv("META_APP_SECRET", raising=False)
    monkeypatch.delenv("META_CONFIGURATION_ID", raising=False)
    get_settings.cache_clear()
    tokens = await _register(client)

    response = await client.get(
        "/api/v1/onboarding/whatsapp/embedded-signup/config", headers=_auth_headers(tokens)
    )

    assert response.status_code == 200
    assert response.json()["configured"] is False
    get_settings.cache_clear()


async def test_embedded_signup_config_reflects_env(client: AsyncClient, monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("META_APP_ID", "app-123")
    monkeypatch.setenv("META_APP_SECRET", "secret")
    monkeypatch.setenv("META_CONFIGURATION_ID", "cfg-1")
    get_settings.cache_clear()
    tokens = await _register(client)

    response = await client.get(
        "/api/v1/onboarding/whatsapp/embedded-signup/config", headers=_auth_headers(tokens)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["app_id"] == "app-123"
    assert body["config_id"] == "cfg-1"
    get_settings.cache_clear()


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None) -> None:
        self.status_code = status_code
        self._json_body = json_body if json_body is not None else {}
        self.text = str(self._json_body)

    def json(self) -> dict:
        return self._json_body


class _FakeSignupClient:
    def __init__(self, responses: dict[str, _FakeResponse]) -> None:
        self._responses = responses

    async def __aenter__(self) -> "_FakeSignupClient":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    def _respond(self, url: str) -> _FakeResponse:
        for suffix, response in self._responses.items():
            if url.endswith(suffix):
                return response
        raise AssertionError(f"unexpected call to {url}")

    async def get(self, url: str, **kwargs: object) -> _FakeResponse:
        return self._respond(url)

    async def post(self, url: str, **kwargs: object) -> _FakeResponse:
        return self._respond(url)


async def test_complete_embedded_signup_endpoint_connects_whatsapp(
    client: AsyncClient, monkeypatch
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("META_APP_ID", "app-123")
    monkeypatch.setenv("META_APP_SECRET", "secret")
    monkeypatch.setenv("META_CONFIGURATION_ID", "cfg-1")
    get_settings.cache_clear()
    tokens = await _register(client)

    fake_client = _FakeSignupClient(
        {
            "/oauth/access_token": _FakeResponse(200, {"access_token": "long-lived-token"}),
            "/phone-1": _FakeResponse(200, {"display_phone_number": "+91 90000 00000"}),
            "/phone-1/register": _FakeResponse(200, {"success": True}),
            "/waba-1/subscribed_apps": _FakeResponse(200, {"success": True}),
        }
    )
    monkeypatch.setattr(
        embedded_signup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client
    )

    response = await client.post(
        "/api/v1/onboarding/whatsapp/embedded-signup/complete",
        json={"code": "auth-code", "waba_id": "waba-1", "phone_number_id": "phone-1"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["connection_status"] == "connected"
    assert body["connection_method"] == "embedded_signup"
    assert body["phone_number_id"] == "phone-1"
    assert body["access_token_set"] is True
    assert "long-lived-token" not in response.text
    get_settings.cache_clear()


async def test_complete_embedded_signup_endpoint_502s_on_meta_failure(
    client: AsyncClient, monkeypatch
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("META_APP_ID", "app-123")
    monkeypatch.setenv("META_APP_SECRET", "secret")
    monkeypatch.setenv("META_CONFIGURATION_ID", "cfg-1")
    get_settings.cache_clear()
    tokens = await _register(client)

    fake_client = _FakeSignupClient(
        {"/oauth/access_token": _FakeResponse(400, {"error": "invalid code"})}
    )
    monkeypatch.setattr(
        embedded_signup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client
    )

    response = await client.post(
        "/api/v1/onboarding/whatsapp/embedded-signup/complete",
        json={"code": "bad-code", "waba_id": "waba-1", "phone_number_id": "phone-1"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 502
    get_settings.cache_clear()
