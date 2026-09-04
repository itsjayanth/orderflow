import base64
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from campaigns.adapters import media_upload as media_upload_module
from campaigns.adapters import template_gateway as template_gateway_module
from campaigns.domain.models import MessageTemplate
from campaigns.domain.template_validation import InvalidTemplateError
from campaigns.domain.template_validation import validate_template as validate_template_fields
from identity.adapters.repository import MerchantRepository
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from shared.encryption import encrypt
from shared.security import decode_token
from shared.tenant import TenantContext

# --- template_validation.py: DOCUMENT's header_filename requirement ---


def test_validate_template_requires_header_filename_for_document() -> None:
    with pytest.raises(InvalidTemplateError):
        validate_template_fields(
            category="MARKETING",
            header_type="DOCUMENT",
            header_text=None,
            body_text="Hi",
            footer_text=None,
            header_filename=None,
        )


def test_validate_template_accepts_document_with_filename() -> None:
    count = validate_template_fields(
        category="MARKETING",
        header_type="DOCUMENT",
        header_text=None,
        body_text="Hi",
        footer_text=None,
        header_filename="menu.pdf",
    )
    assert count == 0


@pytest.mark.parametrize("header_type", ["NONE", "TEXT", "IMAGE", "VIDEO"])
def test_validate_template_rejects_header_filename_outside_document(header_type: str) -> None:
    with pytest.raises(InvalidTemplateError):
        validate_template_fields(
            category="MARKETING",
            header_type=header_type,
            header_text="Promo" if header_type == "TEXT" else None,
            body_text="Hi",
            footer_text=None,
            header_filename="menu.pdf",
        )


# --- media_upload.py: per-kind size/MIME validation ---


async def _make_waba(db_session: AsyncSession):
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


async def test_upload_header_media_rejects_wrong_mime_for_kind(db_session: AsyncSession) -> None:
    _, waba = await _make_waba(db_session)
    with pytest.raises(media_upload_module.MediaUploadError):
        # image/jpeg is valid for "image" but not for "video".
        await media_upload_module.upload_header_media("video", waba, b"data", "image/jpeg")


async def test_upload_header_media_rejects_oversized_video(db_session: AsyncSession) -> None:
    _, waba = await _make_waba(db_session)
    oversized = b"x" * (16 * 1024 * 1024 + 1)
    with pytest.raises(media_upload_module.MediaUploadError):
        await media_upload_module.upload_header_media("video", waba, oversized, "video/mp4")


async def test_upload_header_media_accepts_pdf_for_document(
    db_session: AsyncSession, monkeypatch
) -> None:
    from shared.config import get_settings

    monkeypatch.setenv("META_APP_ID", "test-app-id")
    get_settings.cache_clear()

    _, waba = await _make_waba(db_session)
    fake_client = _FakeMetaClient(
        [
            _FakeResponse(200, {"id": "upload:SESSION_1"}),
            _FakeResponse(200, {"h": "DOC_HANDLE_1"}),
        ]
    )
    monkeypatch.setattr(media_upload_module.httpx, "AsyncClient", lambda **kw: fake_client)

    handle = await media_upload_module.upload_header_media(
        "document", waba, b"%PDF-1.4 fake pdf bytes", "application/pdf"
    )

    assert handle == "DOC_HANDLE_1"
    get_settings.cache_clear()


# --- template_gateway.py: VIDEO/DOCUMENT HEADER component wiring ---


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


async def test_create_template_video_header_matches_image_header_wiring(
    db_session: AsyncSession, monkeypatch
) -> None:
    _, waba = await _make_waba(db_session)
    template = MessageTemplate(
        merchant_id=waba.merchant_id,
        name="promo_video",
        category="MARKETING",
        language_code="en_US",
        header_type="VIDEO",
        header_media_handle="VIDEO_HANDLE_1",
        body_text="Hi",
        body_variable_count=0,
        buttons=[],
    )
    fake_client = _FakeMetaClient([_FakeResponse(200, {"id": "META_V1", "status": "PENDING"})])
    monkeypatch.setattr(template_gateway_module.httpx, "AsyncClient", lambda **kw: fake_client)

    meta_template_id, status = await template_gateway_module.MetaTemplateGateway().create_template(
        waba, template
    )

    assert meta_template_id == "META_V1"
    assert status == "pending"
    payload = fake_client.calls[0]["json"]
    header_component = next(c for c in payload["components"] if c["type"] == "HEADER")
    assert header_component["format"] == "VIDEO"
    assert header_component["example"]["header_handle"] == ["VIDEO_HANDLE_1"]


async def test_create_template_document_header_matches_image_header_wiring(
    db_session: AsyncSession, monkeypatch
) -> None:
    _, waba = await _make_waba(db_session)
    template = MessageTemplate(
        merchant_id=waba.merchant_id,
        name="promo_doc",
        category="MARKETING",
        language_code="en_US",
        header_type="DOCUMENT",
        header_media_handle="DOC_HANDLE_1",
        header_filename="menu.pdf",
        body_text="Hi",
        body_variable_count=0,
        buttons=[],
    )
    fake_client = _FakeMetaClient([_FakeResponse(200, {"id": "META_D1", "status": "PENDING"})])
    monkeypatch.setattr(template_gateway_module.httpx, "AsyncClient", lambda **kw: fake_client)

    meta_template_id, _status = await template_gateway_module.MetaTemplateGateway().create_template(
        waba, template
    )

    assert meta_template_id == "META_D1"
    payload = fake_client.calls[0]["json"]
    header_component = next(c for c in payload["components"] if c["type"] == "HEADER")
    assert header_component["format"] == "DOCUMENT"
    assert header_component["example"]["header_handle"] == ["DOC_HANDLE_1"]


# --- router: full create -> VIDEO template round trip ---


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


async def test_create_video_template_via_api(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    from shared.config import get_settings

    monkeypatch.setenv("META_APP_ID", "test-app-id")
    get_settings.cache_clear()

    tokens = await _register(client)
    payload = decode_token(tokens["access_token"], expected_type="access")
    tenant = TenantContext(merchant_id=uuid.UUID(payload["merchant_id"]))
    await WhatsAppBusinessAccountRepository(db_session).upsert_from_embedded_signup(
        tenant,
        meta_waba_id="WABA_1",
        phone_number_id="PNID1",
        display_phone_number=None,
        access_token_encrypted=encrypt("dummy-token"),
        registration_pin_encrypted=None,
    )
    await db_session.commit()

    upload_client = _FakeMetaClient(
        [
            _FakeResponse(200, {"id": "upload:SESSION_1"}),
            _FakeResponse(200, {"h": "VIDEO_HANDLE_1"}),
        ]
    )
    create_client = _FakeMetaClient([_FakeResponse(200, {"id": "META_V1", "status": "PENDING"})])

    calls = {"n": 0}

    def _client_factory(**kw):
        calls["n"] += 1
        return upload_client if calls["n"] == 1 else create_client

    monkeypatch.setattr(media_upload_module.httpx, "AsyncClient", _client_factory)
    monkeypatch.setattr(template_gateway_module.httpx, "AsyncClient", _client_factory)

    video_b64 = base64.b64encode(b"fake mp4 bytes").decode()
    response = await client.post(
        "/api/v1/campaigns/templates",
        json={
            "name": "Promo video",
            "category": "MARKETING",
            "header_type": "VIDEO",
            "header_media_base64": video_b64,
            "header_media_content_type": "video/mp4",
            "body_text": "Check out our new menu!",
        },
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["header_type"] == "VIDEO"
    assert body["meta_template_id"] == "META_V1"
    get_settings.cache_clear()
