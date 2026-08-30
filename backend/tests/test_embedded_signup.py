from httpx import AsyncClient

from onboarding.domain import embedded_signup as embedded_signup_domain
from shared.config import get_settings


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._json_body = json_body if json_body is not None else {}
        self.text = text or str(self._json_body)

    def json(self) -> dict:
        return self._json_body


class _FakeMetaClient:
    """Same idea as flows/tests' / test_onboarding_whatsapp.py's fakes --
    returns each response in order, letting a test drive the multi-step
    (code exchange / debug_token / display-number lookup / subscribe /
    register) sequence without a real network call."""

    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.calls: list[dict] = []
        self._responses = responses

    async def __aenter__(self) -> "_FakeMetaClient":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def get(self, url: str, **kwargs: object) -> _FakeResponse:
        response = self._responses[len(self.calls)]
        self.calls.append({"method": "get", "url": url, **kwargs})
        return response

    async def post(self, url: str, **kwargs: object) -> _FakeResponse:
        response = self._responses[len(self.calls)]
        self.calls.append({"method": "post", "url": url, **kwargs})
        return response


def _debug_token_ok(waba_id: str) -> _FakeResponse:
    return _FakeResponse(
        200,
        {
            "data": {
                "is_valid": True,
                "granular_scopes": [
                    {"scope": "whatsapp_business_management", "target_ids": [waba_id]}
                ],
            }
        },
    )


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


def _configure_meta_app(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("META_APP_ID", "test-app-id")
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    get_settings.cache_clear()


async def test_embedded_signup_requires_meta_app_configured(
    client: AsyncClient, monkeypatch
) -> None:
    tokens = await _register(client, owner_contact="no-meta-app@example.com")
    monkeypatch.delenv("META_APP_ID", raising=False)
    monkeypatch.delenv("META_APP_SECRET", raising=False)
    get_settings.cache_clear()

    response = await client.post(
        "/api/v1/onboarding/whatsapp/embedded-signup",
        json={"code": "auth-code", "waba_id": "WABA_1", "phone_number_id": "PHONE_1"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 502
    assert "precondition" in response.json()["detail"]
    get_settings.cache_clear()


async def test_embedded_signup_cancel_event_makes_no_meta_calls(
    client: AsyncClient, monkeypatch
) -> None:
    tokens = await _register(client, owner_contact="cancel-event@example.com")
    _configure_meta_app(monkeypatch)

    fake_client = _FakeMetaClient([])  # any call would IndexError
    monkeypatch.setattr(
        embedded_signup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client
    )

    response = await client.post(
        "/api/v1/onboarding/whatsapp/embedded-signup",
        json={"event": "CANCEL"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "not_completed"
    assert fake_client.calls == []
    get_settings.cache_clear()


async def test_embedded_signup_completes_and_persists_credentials(
    client: AsyncClient, monkeypatch
) -> None:
    tokens = await _register(client, owner_contact="es-success@example.com")
    _configure_meta_app(monkeypatch)

    fake_client = _FakeMetaClient(
        [
            _FakeResponse(200, {"access_token": "long-lived-token"}),  # code exchange
            _debug_token_ok("WABA_1"),  # debug_token
            _FakeResponse(200, {"display_phone_number": "+91 90000 00000"}),  # display number
            _FakeResponse(200, {"success": True}),  # subscribe app to WABA
            _FakeResponse(200, {"success": True}),  # register phone number
        ]
    )
    monkeypatch.setattr(
        embedded_signup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client
    )

    response = await client.post(
        "/api/v1/onboarding/whatsapp/embedded-signup",
        json={
            "code": "auth-code",
            "waba_id": "WABA_1",
            "phone_number_id": "PHONE_1",
            "business_id": "BIZ_1",
            "event": "FINISH",
        },
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "connected"
    assert body["phone_number_id"] == "PHONE_1"
    assert body["display_phone_number"] == "+91 90000 00000"
    assert body["pending_steps"] == []
    # The raw access token is never echoed back.
    assert "long-lived-token" not in response.text

    settings_response = await client.get(
        "/api/v1/onboarding/whatsapp", headers=_auth_headers(tokens)
    )
    settings_body = settings_response.json()
    assert settings_body["connection_status"] == "connected"
    assert settings_body["phone_number_id"] == "PHONE_1"
    assert settings_body["access_token_set"] is True
    get_settings.cache_clear()


async def test_embedded_signup_subscribes_with_orderflows_own_override_callback_uri(
    client: AsyncClient, monkeypatch
) -> None:
    """The Meta App backing Embedded Signup is shared with fastflow/ORDZO
    (see shared/config.py's meta_app_id docstring) -- without an explicit
    override_callback_uri, Meta would route orderflow's WABA webhook
    events to fastflow's app-level default Callback URL instead. This
    must never regress silently."""
    tokens = await _register(client, owner_contact="es-override-uri@example.com")
    _configure_meta_app(monkeypatch)

    fake_client = _FakeMetaClient(
        [
            _FakeResponse(200, {"access_token": "long-lived-token"}),  # code exchange
            _debug_token_ok("WABA_1"),  # debug_token
            _FakeResponse(200, {"display_phone_number": "+91 90000 00000"}),  # display number
            _FakeResponse(200, {"success": True}),  # subscribe app to WABA
            _FakeResponse(200, {"success": True}),  # register phone number
        ]
    )
    monkeypatch.setattr(
        embedded_signup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client
    )

    response = await client.post(
        "/api/v1/onboarding/whatsapp/embedded-signup",
        json={
            "code": "auth-code",
            "waba_id": "WABA_1",
            "phone_number_id": "PHONE_1",
            "event": "FINISH",
            "backend_base_url": "https://orderflow-backend.example.com/",
        },
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200, response.text
    subscribe_call = next(
        call for call in fake_client.calls if "/WABA_1/subscribed_apps" in call["url"]
    )
    assert subscribe_call["json"]["override_callback_uri"] == (
        "https://orderflow-backend.example.com/api/v1/whatsapp/webhook"
    )
    assert subscribe_call["json"]["verify_token"] == get_settings().whatsapp_webhook_verify_token
    get_settings.cache_clear()


async def test_embedded_signup_persists_credentials_even_if_registration_fails(
    client: AsyncClient, monkeypatch
) -> None:
    """Deferred Meta-side steps (webhook subscribe, phone register) are
    best-effort and must never roll back an already-verified token -- a
    half-set-up store recoverable via retry is better than discarding a
    working credential."""
    tokens = await _register(client, owner_contact="es-partial-fail@example.com")
    _configure_meta_app(monkeypatch)

    fake_client = _FakeMetaClient(
        [
            _FakeResponse(200, {"access_token": "long-lived-token"}),  # code exchange
            _debug_token_ok("WABA_1"),  # debug_token
            _FakeResponse(200, {"display_phone_number": "+91 90000 00000"}),  # display number
            _FakeResponse(400, {"error": {"message": "subscribe failed"}}),  # subscribe fails
            _FakeResponse(400, {"error": {"message": "register failed"}}),  # register fails
        ]
    )
    monkeypatch.setattr(
        embedded_signup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client
    )

    response = await client.post(
        "/api/v1/onboarding/whatsapp/embedded-signup",
        json={"code": "auth-code", "waba_id": "WABA_1", "phone_number_id": "PHONE_1"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "connected"
    assert set(body["pending_steps"]) == {"webhook_subscription", "phone_number_registration"}

    settings_response = await client.get(
        "/api/v1/onboarding/whatsapp", headers=_auth_headers(tokens)
    )
    assert settings_response.json()["access_token_set"] is True
    get_settings.cache_clear()


async def test_embedded_signup_rejects_token_not_scoped_to_waba(
    client: AsyncClient, monkeypatch
) -> None:
    tokens = await _register(client, owner_contact="es-scope-mismatch@example.com")
    _configure_meta_app(monkeypatch)

    fake_client = _FakeMetaClient(
        [
            _FakeResponse(200, {"access_token": "long-lived-token"}),  # code exchange
            _debug_token_ok("SOME_OTHER_WABA"),  # debug_token, wrong WABA
        ]
    )
    monkeypatch.setattr(
        embedded_signup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client
    )

    response = await client.post(
        "/api/v1/onboarding/whatsapp/embedded-signup",
        json={"code": "auth-code", "waba_id": "WABA_1", "phone_number_id": "PHONE_1"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 502
    assert "verify_token" in response.json()["detail"]

    settings_response = await client.get(
        "/api/v1/onboarding/whatsapp", headers=_auth_headers(tokens)
    )
    assert settings_response.json()["access_token_set"] is False
    get_settings.cache_clear()


async def test_embedded_signup_finish_only_waba_skips_phone_number(
    client: AsyncClient, monkeypatch
) -> None:
    tokens = await _register(client, owner_contact="es-only-waba@example.com")
    _configure_meta_app(monkeypatch)

    fake_client = _FakeMetaClient(
        [
            _FakeResponse(200, {"access_token": "long-lived-token"}),  # code exchange
            _debug_token_ok("WABA_1"),  # debug_token
            _FakeResponse(200, {"success": True}),  # subscribe app (no phone lookup/register)
        ]
    )
    monkeypatch.setattr(
        embedded_signup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client
    )

    response = await client.post(
        "/api/v1/onboarding/whatsapp/embedded-signup",
        json={"code": "auth-code", "waba_id": "WABA_1", "event": "FINISH_ONLY_WABA"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "connected"
    assert body["phone_number_id"] is None
    assert len(fake_client.calls) == 3
    get_settings.cache_clear()
