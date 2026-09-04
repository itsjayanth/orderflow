import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from campaigns.adapters import media_upload as media_upload_module
from campaigns.adapters import template_gateway as template_gateway_module
from campaigns.adapters.repository import MessageTemplateRepository
from campaigns.domain.models import MessageTemplate
from campaigns.domain.template_status import apply_template_status_update
from campaigns.domain.template_validation import InvalidTemplateError, normalize_template_name
from campaigns.domain.template_validation import validate_template as validate_template_fields
from conversation.domain.webhook_parser import (
    TemplateStatusUpdate,
    parse_template_status_updates,
)
from identity.adapters.repository import MerchantRepository
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from shared.encryption import encrypt
from shared.security import decode_token
from shared.tenant import TenantContext

# --- template_validation.py ---


def test_normalize_template_name_lowercases_and_snake_cases() -> None:
    assert normalize_template_name("Order Promo!") == "order_promo"


def test_normalize_template_name_rejects_empty_result() -> None:
    with pytest.raises(InvalidTemplateError):
        normalize_template_name("!!!")


@pytest.mark.parametrize("body", ["Hi {{1}}, {{2}}% off today!", "Hello there, no variables."])
def test_validate_template_accepts_sequential_or_no_variables(body: str) -> None:
    count = validate_template_fields(
        category="MARKETING", header_type="NONE", header_text=None, body_text=body, footer_text=None
    )
    assert count == body.count("{{")


@pytest.mark.parametrize(
    "body",
    [
        "Hi {{1}}, {{3}}% off",  # gap
        "Hi {{2}}, {{2}}% off",  # duplicate, not starting at 1
        "Hi {{0}}% off",  # doesn't start at 1
    ],
)
def test_validate_template_rejects_non_sequential_variables(body: str) -> None:
    with pytest.raises(InvalidTemplateError):
        validate_template_fields(
            category="MARKETING",
            header_type="NONE",
            header_text=None,
            body_text=body,
            footer_text=None,
        )


def test_validate_template_rejects_unknown_category() -> None:
    with pytest.raises(InvalidTemplateError):
        validate_template_fields(
            category="PROMO", header_type="NONE", header_text=None, body_text="Hi", footer_text=None
        )


def test_validate_template_requires_header_text_for_text_header() -> None:
    with pytest.raises(InvalidTemplateError):
        validate_template_fields(
            category="MARKETING",
            header_type="TEXT",
            header_text=None,
            body_text="Hi",
            footer_text=None,
        )


def test_validate_template_rejects_header_text_outside_text_header() -> None:
    with pytest.raises(InvalidTemplateError):
        validate_template_fields(
            category="MARKETING",
            header_type="NONE",
            header_text="Promo",
            body_text="Hi",
            footer_text=None,
        )


def test_validate_template_enforces_length_caps() -> None:
    with pytest.raises(InvalidTemplateError):
        validate_template_fields(
            category="MARKETING",
            header_type="NONE",
            header_text=None,
            body_text="x" * 1025,
            footer_text=None,
        )


# --- webhook_parser.py: parse_template_status_updates ---


def test_parse_template_status_updates_approved() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "field": "message_template_status_update",
                        "value": {
                            "message_template_id": "123",
                            "event": "APPROVED",
                        },
                    }
                ]
            }
        ]
    }
    updates = parse_template_status_updates(payload)
    assert updates == [TemplateStatusUpdate(meta_template_id="123", status="approved", reason=None)]


def test_parse_template_status_updates_rejected_carries_reason() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "field": "message_template_status_update",
                        "value": {
                            "message_template_id": "456",
                            "event": "REJECTED",
                            "reason": "INVALID_FORMAT",
                        },
                    }
                ]
            }
        ]
    }
    updates = parse_template_status_updates(payload)
    assert updates[0].status == "rejected"
    assert updates[0].reason == "INVALID_FORMAT"


def test_parse_template_status_updates_ignores_unrelated_field() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {"messages": []},
                    }
                ]
            }
        ]
    }
    assert parse_template_status_updates(payload) == []


def test_parse_template_status_updates_ignores_unrecognized_event() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "field": "message_template_status_update",
                        "value": {"message_template_id": "789", "event": "IN_APPEAL"},
                    }
                ]
            }
        ]
    }
    assert parse_template_status_updates(payload) == []


# --- template_status.py: apply_template_status_update ---


async def test_apply_template_status_update_flips_local_row(db_session: AsyncSession) -> None:
    merchant = await MerchantRepository(db_session).create(
        business_name="Test Business", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    template = await MessageTemplateRepository(db_session).create(
        tenant,
        name="promo",
        category="MARKETING",
        language_code="en_US",
        header_type="NONE",
        header_text=None,
        header_media_handle=None,
        body_text="Hi",
        body_variable_count=0,
        footer_text=None,
        buttons=[],
    )
    await MessageTemplateRepository(db_session).set_meta_submission_result(
        template, meta_template_id="META123", status="pending"
    )
    await db_session.commit()

    await apply_template_status_update(
        db_session, TemplateStatusUpdate(meta_template_id="META123", status="approved", reason=None)
    )
    await db_session.commit()

    refreshed = await MessageTemplateRepository(db_session).get(tenant, template.template_id)
    assert refreshed is not None
    assert refreshed.meta_approval_status == "approved"


async def test_apply_template_status_update_for_unknown_template_is_a_noop(
    db_session: AsyncSession,
) -> None:
    # Should not raise -- a template deleted locally (or belonging to a
    # different Meta App) has nothing here to update.
    await apply_template_status_update(
        db_session, TemplateStatusUpdate(meta_template_id="does-not-exist", status="approved")
    )


# --- MetaTemplateGateway: request-shape against a fake httpx transport ---


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._json_body = json_body if json_body is not None else {}
        self.text = text or str(self._json_body)

    def json(self) -> dict:
        return self._json_body


class _FakeMetaClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.calls: list[dict] = []
        self._responses = responses

    async def __aenter__(self) -> "_FakeMetaClient":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def post(self, url: str, **kwargs: object) -> _FakeResponse:
        response = self._responses[len(self.calls)]
        self.calls.append({"method": "post", "url": url, **kwargs})
        return response

    async def delete(self, url: str, **kwargs: object) -> _FakeResponse:
        response = self._responses[len(self.calls)]
        self.calls.append({"method": "delete", "url": url, **kwargs})
        return response


async def _make_waba(db_session: AsyncSession) -> tuple[TenantContext, object]:
    merchant = await MerchantRepository(db_session).create(
        business_name="Test Business", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    waba = await WhatsAppBusinessAccountRepository(db_session).upsert_from_embedded_signup(
        tenant,
        meta_waba_id="WABA_1",
        phone_number_id="PHONE_1",
        display_phone_number=None,
        access_token_encrypted=encrypt("dummy-token"),
        registration_pin_encrypted=None,
    )
    await db_session.commit()
    return tenant, waba


async def test_create_template_sends_expected_payload_and_wires_header_handle(
    db_session: AsyncSession, monkeypatch
) -> None:
    tenant, waba = await _make_waba(db_session)
    template = MessageTemplate(
        merchant_id=tenant.merchant_id,
        name="order_promo",
        category="MARKETING",
        language_code="en_US",
        header_type="IMAGE",
        header_media_handle="HANDLE_123",
        body_text="Hi {{1}}, {{2}}% off today!",
        body_variable_count=2,
        buttons=[],
    )

    fake_client = _FakeMetaClient(
        [_FakeResponse(200, {"id": "META_TEMPLATE_1", "status": "PENDING"})]
    )
    monkeypatch.setattr(template_gateway_module.httpx, "AsyncClient", lambda **kw: fake_client)

    meta_template_id, status = await template_gateway_module.MetaTemplateGateway().create_template(
        waba, template
    )

    assert meta_template_id == "META_TEMPLATE_1"
    assert status == "pending"
    assert len(fake_client.calls) == 1
    call = fake_client.calls[0]
    assert call["url"] == "https://graph.facebook.com/v22.0/WABA_1/message_templates"
    assert call["headers"]["Authorization"] == "Bearer dummy-token"
    payload = call["json"]
    assert payload["name"] == "order_promo"
    assert payload["category"] == "MARKETING"
    header_component = next(c for c in payload["components"] if c["type"] == "HEADER")
    assert header_component["example"]["header_handle"] == ["HANDLE_123"]
    body_component = next(c for c in payload["components"] if c["type"] == "BODY")
    assert body_component["example"]["body_text"] == [["example1", "example2"]]


async def test_delete_template_calls_meta_before_local_delete(
    db_session: AsyncSession, monkeypatch
) -> None:
    tenant, waba = await _make_waba(db_session)
    fake_client = _FakeMetaClient([_FakeResponse(200, {"success": True})])
    monkeypatch.setattr(template_gateway_module.httpx, "AsyncClient", lambda **kw: fake_client)

    await template_gateway_module.MetaTemplateGateway().delete_template(waba, "META_TEMPLATE_1")

    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["method"] == "delete"
    assert fake_client.calls[0]["params"] == {"hsm_id": "META_TEMPLATE_1"}


# --- media_upload.py ---


async def test_upload_header_image_rejects_unsupported_content_type(
    db_session: AsyncSession,
) -> None:
    _, waba = await _make_waba(db_session)
    with pytest.raises(media_upload_module.MediaUploadError):
        await media_upload_module.upload_header_media("image", waba, b"data", "image/webp")


async def test_upload_header_image_returns_handle(db_session: AsyncSession, monkeypatch) -> None:
    from shared.config import get_settings

    monkeypatch.setenv("META_APP_ID", "test-app-id")
    get_settings.cache_clear()

    _, waba = await _make_waba(db_session)
    fake_client = _FakeMetaClient(
        [
            _FakeResponse(200, {"id": "upload:SESSION_1"}),
            _FakeResponse(200, {"h": "HEADER_HANDLE_1"}),
        ]
    )
    monkeypatch.setattr(media_upload_module.httpx, "AsyncClient", lambda **kw: fake_client)

    handle = await media_upload_module.upload_header_media(
        "image", waba, b"fake-image-bytes", "image/jpeg"
    )

    assert handle == "HEADER_HANDLE_1"
    assert len(fake_client.calls) == 2
    get_settings.cache_clear()


# --- router: full create -> pending -> webhook -> approved round trip ---


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


async def test_create_template_then_webhook_flips_to_approved_with_no_polling(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    tokens = await _register(client)

    payload = decode_token(tokens["access_token"], expected_type="access")
    tenant = TenantContext(merchant_id=uuid.UUID(payload["merchant_id"]))
    await WhatsAppBusinessAccountRepository(db_session).upsert_from_embedded_signup(
        tenant,
        meta_waba_id="WABA_1",
        phone_number_id="PHONE_1",
        display_phone_number=None,
        access_token_encrypted=encrypt("dummy-token"),
        registration_pin_encrypted=None,
    )
    await db_session.commit()

    fake_client = _FakeMetaClient(
        [_FakeResponse(200, {"id": "META_TEMPLATE_1", "status": "PENDING"})]
    )
    monkeypatch.setattr(template_gateway_module.httpx, "AsyncClient", lambda **kw: fake_client)

    create_response = await client.post(
        "/api/v1/campaigns/templates",
        json={
            "name": "Order Promo",
            "category": "MARKETING",
            "body_text": "Hi there, check out today's deals!",
        },
        headers=_auth_headers(tokens),
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["name"] == "order_promo"
    assert created["meta_template_id"] == "META_TEMPLATE_1"
    assert created["meta_approval_status"] == "pending"

    webhook_response = await client.post(
        "/api/v1/whatsapp/webhook",
        json={
            "entry": [
                {
                    "changes": [
                        {
                            "field": "message_template_status_update",
                            "value": {
                                "message_template_id": "META_TEMPLATE_1",
                                "event": "APPROVED",
                            },
                        }
                    ]
                }
            ]
        },
    )
    assert webhook_response.status_code == 200

    # No polling call was made -- the fake client only ever saw the one
    # create_template call above.
    assert len(fake_client.calls) == 1

    get_response = await client.get(
        f"/api/v1/campaigns/templates/{created['template_id']}", headers=_auth_headers(tokens)
    )
    assert get_response.json()["meta_approval_status"] == "approved"


async def test_templates_are_tenant_isolated(client: AsyncClient, monkeypatch) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    tokens_b = await _register(client, owner_contact="owner-b@example.com")

    list_response = await client.get("/api/v1/campaigns/templates", headers=_auth_headers(tokens_b))
    assert list_response.json() == []

    # A merchant with no connected WhatsApp gets a 422, not a crash -- also
    # proves tenant_a's absence doesn't matter to tenant_b's own request.
    create_response = await client.post(
        "/api/v1/campaigns/templates",
        json={"name": "promo", "category": "MARKETING", "body_text": "Hi"},
        headers=_auth_headers(tokens_a),
    )
    assert create_response.status_code == 422
