from httpx import AsyncClient

from flows.domain import setup as flow_setup_domain


class _FakeFlowSetupResponse:
    def __init__(self, status_code: int, text: str = "", json_body: dict | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self._json_body = json_body if json_body is not None else {}

    def json(self) -> dict:
        return self._json_body


class _FakeFlowSetupClient:
    """Same idea as flows/tests' fakes -- returns each response in order,
    letting a test drive setup_whatsapp_appointment_flow's multi-step
    (upload key / create flow / upload json / publish) sequence without a
    real network call."""

    def __init__(self, responses: list[_FakeFlowSetupResponse]) -> None:
        self.calls: list[dict] = []
        self._responses = responses

    async def __aenter__(self) -> "_FakeFlowSetupClient":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def post(self, url: str, **kwargs: object) -> _FakeFlowSetupResponse:
        response = self._responses[len(self.calls)]
        self.calls.append({"method": "post", "url": url, **kwargs})
        return response

    async def get(self, url: str, **kwargs: object) -> _FakeFlowSetupResponse:
        response = self._responses[len(self.calls)]
        self.calls.append({"method": "get", "url": url, **kwargs})
        return response


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
    tokens = response.json()
    # New first wizard step (MULTI_VERTICAL_PLAN.md Phase M1) -- must
    # happen before WhatsApp connection, same as production onboarding.
    vertical_response = await client.put(
        "/api/v1/onboarding/verticals",
        json={"restaurant_enabled": True, "appointment_enabled": False},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert vertical_response.status_code == 200, vertical_response.text
    return tokens


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


async def test_appointment_flow_setup_requires_whatsapp_credentials(client: AsyncClient) -> None:
    tokens = await _register(client, owner_contact="no-creds-appt@example.com")

    response = await client.post(
        "/api/v1/onboarding/whatsapp/appointment-flow-setup",
        json={"meta_waba_id": "123", "backend_base_url": "https://example.com"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 400


async def test_appointment_flow_setup_persists_flow_id(client: AsyncClient, monkeypatch) -> None:
    tokens = await _register(client, owner_contact="appt-setup@example.com")
    await client.put(
        "/api/v1/onboarding/whatsapp",
        json={"phone_number_id": "1234567890", "access_token": "dummy-meta-access-token"},
        headers=_auth_headers(tokens),
    )

    fake_client = _FakeFlowSetupClient(
        [
            _FakeFlowSetupResponse(200),  # upload_public_key
            _FakeFlowSetupResponse(200, json_body={"id": "APPT_FLOW_ENDPOINT"}),  # create_flow
            _FakeFlowSetupResponse(200),  # upload_flow_json
            _FakeFlowSetupResponse(200),  # publish
        ]
    )
    monkeypatch.setattr(flow_setup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client)

    response = await client.post(
        "/api/v1/onboarding/whatsapp/appointment-flow-setup",
        json={"meta_waba_id": "META_WABA_1", "backend_base_url": "https://example.com"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"flow_id": "APPT_FLOW_ENDPOINT"}


async def test_appointment_flow_setup_reports_meta_failure_as_bad_gateway(
    client: AsyncClient, monkeypatch
) -> None:
    tokens = await _register(client, owner_contact="appt-setup-fail@example.com")
    await client.put(
        "/api/v1/onboarding/whatsapp",
        json={"phone_number_id": "1234567890", "access_token": "dummy-meta-access-token"},
        headers=_auth_headers(tokens),
    )

    fake_client = _FakeFlowSetupClient([_FakeFlowSetupResponse(400, "key rejected")])
    monkeypatch.setattr(flow_setup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client)

    response = await client.post(
        "/api/v1/onboarding/whatsapp/appointment-flow-setup",
        json={"meta_waba_id": "META_WABA_1", "backend_base_url": "https://example.com"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 502
    assert "upload_public_key" in response.json()["detail"]


async def test_appointment_flow_sync_requires_flow_setup_first(client: AsyncClient) -> None:
    tokens = await _register(client, owner_contact="appt-sync-no-flow@example.com")
    await client.put(
        "/api/v1/onboarding/whatsapp",
        json={"phone_number_id": "1234567890", "access_token": "dummy-meta-access-token"},
        headers=_auth_headers(tokens),
    )

    response = await client.post(
        "/api/v1/onboarding/whatsapp/appointment-flow-sync", headers=_auth_headers(tokens)
    )

    assert response.status_code == 502
    assert "precondition" in response.json()["detail"]


async def test_appointment_flow_sync_returns_validation(client: AsyncClient, monkeypatch) -> None:
    tokens = await _register(client, owner_contact="appt-sync@example.com")
    await client.put(
        "/api/v1/onboarding/whatsapp",
        json={"phone_number_id": "1234567890", "access_token": "dummy-meta-access-token"},
        headers=_auth_headers(tokens),
    )
    fake_setup_client = _FakeFlowSetupClient(
        [
            _FakeFlowSetupResponse(200),
            _FakeFlowSetupResponse(200, json_body={"id": "APPT_FLOW_SYNC"}),
            _FakeFlowSetupResponse(200),
            _FakeFlowSetupResponse(200),
        ]
    )
    monkeypatch.setattr(flow_setup_domain.httpx, "AsyncClient", lambda **kwargs: fake_setup_client)
    setup_response = await client.post(
        "/api/v1/onboarding/whatsapp/appointment-flow-setup",
        json={"meta_waba_id": "META_WABA_1", "backend_base_url": "https://example.com"},
        headers=_auth_headers(tokens),
    )
    assert setup_response.status_code == 200, setup_response.text

    validation_body = {
        "status": "PUBLISHED",
        "validation_errors": [],
        "health_status": {"can_send_message": "AVAILABLE"},
    }
    fake_sync_client = _FakeFlowSetupClient(
        [
            _FakeFlowSetupResponse(200),  # upload_flow_json
            _FakeFlowSetupResponse(200),  # publish
            _FakeFlowSetupResponse(200, json_body=validation_body),  # get_flow_validation
        ]
    )
    monkeypatch.setattr(flow_setup_domain.httpx, "AsyncClient", lambda **kwargs: fake_sync_client)

    response = await client.post(
        "/api/v1/onboarding/whatsapp/appointment-flow-sync", headers=_auth_headers(tokens)
    )

    assert response.status_code == 200, response.text
    assert response.json() == validation_body
    assert fake_sync_client.calls[-1]["url"].endswith("/APPT_FLOW_SYNC")
