import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from flows.domain import setup as flow_setup_domain
from flows.domain.setup import (
    FlowSetupError,
    get_flow_validation,
    setup_whatsapp_appointment_flow,
    setup_whatsapp_flow,
    update_appointment_flow_assets,
    update_flow_assets,
)
from identity.adapters.repository import MerchantRepository
from onboarding.domain.models import WhatsAppBusinessAccount
from shared.encryption import encrypt
from shared.tenant import TenantContext


async def test_setup_fails_precondition_without_credentials(db_session: AsyncSession) -> None:
    merchant = await MerchantRepository(db_session).create(
        business_name="No Creds Yet", owner_contact="nocreds@example.com"
    )
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    # A WABA row with no phone_number_id/access_token -- the case where the
    # caller (the API router 400s before calling in) already found *some*
    # row to pass in, but it's incomplete.
    account = WhatsAppBusinessAccount(merchant_id=merchant.merchant_id)
    db_session.add(account)
    await db_session.commit()

    with pytest.raises(FlowSetupError) as exc_info:
        await setup_whatsapp_flow(
            db_session,
            tenant,
            account,
            meta_waba_id="123",
            backend_base_url="https://example.com",
        )

    assert exc_info.value.step == "precondition"


async def test_setup_appointment_flow_fails_precondition_without_credentials(
    db_session: AsyncSession,
) -> None:
    merchant = await MerchantRepository(db_session).create(
        business_name="No Appt Creds Yet", owner_contact="nocreds-appt@example.com"
    )
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    account = WhatsAppBusinessAccount(merchant_id=merchant.merchant_id)
    db_session.add(account)
    await db_session.commit()

    with pytest.raises(FlowSetupError) as exc_info:
        await setup_whatsapp_appointment_flow(
            db_session,
            tenant,
            account,
            meta_waba_id="123",
            backend_base_url="https://example.com",
        )

    assert exc_info.value.step == "precondition"


async def _seed_merchant_tenant(db_session: AsyncSession, business_name: str) -> TenantContext:
    merchant = await MerchantRepository(db_session).create(
        business_name=business_name, owner_contact=f"{business_name}@example.com"
    )
    return TenantContext(merchant_id=merchant.merchant_id)


async def test_update_flow_assets_fails_precondition_without_flow_id(
    db_session: AsyncSession,
) -> None:
    tenant = await _seed_merchant_tenant(db_session, "No Flow Yet")
    account = WhatsAppBusinessAccount(
        merchant_id=tenant.merchant_id, access_token_encrypted=encrypt("dummy-token")
    )
    db_session.add(account)
    await db_session.commit()

    with pytest.raises(FlowSetupError) as exc_info:
        await update_flow_assets(db_session, tenant, account)

    assert exc_info.value.step == "precondition"


async def test_update_flow_assets_fails_precondition_without_access_token(
    db_session: AsyncSession,
) -> None:
    tenant = await _seed_merchant_tenant(db_session, "No Token Yet")
    account = WhatsAppBusinessAccount(merchant_id=tenant.merchant_id, whatsapp_flow_id="FLOW_1")
    db_session.add(account)
    await db_session.commit()

    with pytest.raises(FlowSetupError) as exc_info:
        await update_flow_assets(db_session, tenant, account)

    assert exc_info.value.step == "precondition"


class _FakeAssetUploadResponse:
    def __init__(self, status_code: int, text: str = "", json_body: dict | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self._json_body = json_body if json_body is not None else {}

    def json(self) -> dict:
        return self._json_body


class _FakeAssetUploadClient:
    """Records every POST/GET made against it -- lets a test assert
    update_flow_assets/get_flow_validation hit the right Meta endpoint
    with the right flow_id, without a real network call."""

    def __init__(self, response: _FakeAssetUploadResponse) -> None:
        self.calls: list[dict] = []
        self._response = response

    async def __aenter__(self) -> "_FakeAssetUploadClient":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def post(self, url: str, **kwargs: object) -> _FakeAssetUploadResponse:
        self.calls.append({"method": "post", "url": url, **kwargs})
        return self._response

    async def get(self, url: str, **kwargs: object) -> _FakeAssetUploadResponse:
        self.calls.append({"method": "get", "url": url, **kwargs})
        return self._response


async def test_update_flow_assets_uploads_flow_json(db_session: AsyncSession, monkeypatch) -> None:
    tenant = await _seed_merchant_tenant(db_session, "Already Set Up")
    account = WhatsAppBusinessAccount(
        merchant_id=tenant.merchant_id,
        whatsapp_flow_id="FLOW_42",
        access_token_encrypted=encrypt("dummy-token"),
    )
    db_session.add(account)
    await db_session.commit()

    fake_client = _FakeAssetUploadClient(_FakeAssetUploadResponse(200))
    monkeypatch.setattr(flow_setup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client)

    await update_flow_assets(db_session, tenant, account)

    assert len(fake_client.calls) == 2
    assert fake_client.calls[0]["url"].endswith("/FLOW_42/assets")
    assert fake_client.calls[0]["data"] == {"name": "flow.json", "asset_type": "FLOW_JSON"}
    assert fake_client.calls[1]["url"].endswith("/FLOW_42/publish")


async def test_update_flow_assets_raises_on_upload_failure(
    db_session: AsyncSession, monkeypatch
) -> None:
    tenant = await _seed_merchant_tenant(db_session, "Upload Fails")
    account = WhatsAppBusinessAccount(
        merchant_id=tenant.merchant_id,
        whatsapp_flow_id="FLOW_42",
        access_token_encrypted=encrypt("dummy-token"),
    )
    db_session.add(account)
    await db_session.commit()

    fake_client = _FakeAssetUploadClient(_FakeAssetUploadResponse(400, "bad request"))
    monkeypatch.setattr(flow_setup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client)

    with pytest.raises(FlowSetupError) as exc_info:
        await update_flow_assets(db_session, tenant, account)

    assert exc_info.value.step == "upload_flow_json"


class _FakeSequencedClient:
    """Like _FakeAssetUploadClient, but returns a different response per
    call in order -- needed to test update_flow_assets' two-step
    upload-then-publish sequence independently (e.g. upload succeeds but
    publish fails)."""

    def __init__(self, responses: list[_FakeAssetUploadResponse]) -> None:
        self.calls: list[dict] = []
        self._responses = responses

    async def __aenter__(self) -> "_FakeSequencedClient":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def post(self, url: str, **kwargs: object) -> _FakeAssetUploadResponse:
        response = self._responses[len(self.calls)]
        self.calls.append({"method": "post", "url": url, **kwargs})
        return response


async def test_update_flow_assets_raises_on_publish_failure(
    db_session: AsyncSession, monkeypatch
) -> None:
    tenant = await _seed_merchant_tenant(db_session, "Publish Fails")
    account = WhatsAppBusinessAccount(
        merchant_id=tenant.merchant_id,
        whatsapp_flow_id="FLOW_42",
        access_token_encrypted=encrypt("dummy-token"),
    )
    db_session.add(account)
    await db_session.commit()

    fake_client = _FakeSequencedClient(
        [_FakeAssetUploadResponse(200), _FakeAssetUploadResponse(400, "publish rejected")]
    )
    monkeypatch.setattr(flow_setup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client)

    with pytest.raises(FlowSetupError) as exc_info:
        await update_flow_assets(db_session, tenant, account)

    assert exc_info.value.step == "publish_flow"
    assert len(fake_client.calls) == 2
    assert fake_client.calls[1]["url"].endswith("/FLOW_42/publish")


async def test_setup_appointment_flow_persists_credentials_and_publishes(
    db_session: AsyncSession, monkeypatch
) -> None:
    tenant = await _seed_merchant_tenant(db_session, "Appt Setup Success")
    account = WhatsAppBusinessAccount(
        merchant_id=tenant.merchant_id,
        phone_number_id="PHONE_1",
        access_token_encrypted=encrypt("dummy-token"),
    )
    db_session.add(account)
    await db_session.commit()

    fake_client = _FakeSequencedClient(
        [
            _FakeAssetUploadResponse(200),  # upload_public_key
            _FakeAssetUploadResponse(200, json_body={"id": "APPT_FLOW_99"}),  # create_flow
            _FakeAssetUploadResponse(200),  # upload_flow_json
            _FakeAssetUploadResponse(200),  # publish
        ]
    )
    monkeypatch.setattr(flow_setup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client)

    flow_id = await setup_whatsapp_appointment_flow(
        db_session,
        tenant,
        account,
        meta_waba_id="META_WABA_1",
        backend_base_url="https://example.com",
    )

    assert flow_id == "APPT_FLOW_99"
    assert account.whatsapp_appointment_flow_id == "APPT_FLOW_99"
    assert account.flow_private_key_encrypted is not None

    assert len(fake_client.calls) == 4
    assert fake_client.calls[0]["url"].endswith("/PHONE_1/whatsapp_business_encryption")
    assert fake_client.calls[1]["url"].endswith("/META_WABA_1/flows")
    assert fake_client.calls[1]["json"]["name"] == "Book an Appointment"
    assert fake_client.calls[1]["json"]["categories"] == ["OTHER"]
    assert fake_client.calls[1]["json"]["endpoint_uri"] == (
        f"https://example.com/api/v1/whatsapp/flows/{tenant.merchant_id}/appointment-data-exchange"
    )
    assert fake_client.calls[2]["url"].endswith("/APPT_FLOW_99/assets")
    assert fake_client.calls[3]["url"].endswith("/APPT_FLOW_99/publish")


async def test_update_appointment_flow_assets_fails_precondition_without_flow_id(
    db_session: AsyncSession,
) -> None:
    tenant = await _seed_merchant_tenant(db_session, "No Appt Flow Yet")
    account = WhatsAppBusinessAccount(
        merchant_id=tenant.merchant_id, access_token_encrypted=encrypt("dummy-token")
    )
    db_session.add(account)
    await db_session.commit()

    with pytest.raises(FlowSetupError) as exc_info:
        await update_appointment_flow_assets(db_session, tenant, account)

    assert exc_info.value.step == "precondition"


async def test_update_appointment_flow_assets_fails_precondition_without_access_token(
    db_session: AsyncSession,
) -> None:
    tenant = await _seed_merchant_tenant(db_session, "No Appt Token Yet")
    account = WhatsAppBusinessAccount(
        merchant_id=tenant.merchant_id, whatsapp_appointment_flow_id="APPT_FLOW_1"
    )
    db_session.add(account)
    await db_session.commit()

    with pytest.raises(FlowSetupError) as exc_info:
        await update_appointment_flow_assets(db_session, tenant, account)

    assert exc_info.value.step == "precondition"


async def test_update_appointment_flow_assets_uploads_flow_json(
    db_session: AsyncSession, monkeypatch
) -> None:
    tenant = await _seed_merchant_tenant(db_session, "Appt Already Set Up")
    account = WhatsAppBusinessAccount(
        merchant_id=tenant.merchant_id,
        whatsapp_appointment_flow_id="APPT_FLOW_42",
        access_token_encrypted=encrypt("dummy-token"),
    )
    db_session.add(account)
    await db_session.commit()

    fake_client = _FakeAssetUploadClient(_FakeAssetUploadResponse(200))
    monkeypatch.setattr(flow_setup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client)

    await update_appointment_flow_assets(db_session, tenant, account)

    assert len(fake_client.calls) == 2
    assert fake_client.calls[0]["url"].endswith("/APPT_FLOW_42/assets")
    assert fake_client.calls[0]["data"] == {"name": "flow.json", "asset_type": "FLOW_JSON"}
    assert fake_client.calls[1]["url"].endswith("/APPT_FLOW_42/publish")


async def test_update_appointment_flow_assets_raises_on_publish_failure(
    db_session: AsyncSession, monkeypatch
) -> None:
    tenant = await _seed_merchant_tenant(db_session, "Appt Publish Fails")
    account = WhatsAppBusinessAccount(
        merchant_id=tenant.merchant_id,
        whatsapp_appointment_flow_id="APPT_FLOW_42",
        access_token_encrypted=encrypt("dummy-token"),
    )
    db_session.add(account)
    await db_session.commit()

    fake_client = _FakeSequencedClient(
        [_FakeAssetUploadResponse(200), _FakeAssetUploadResponse(400, "publish rejected")]
    )
    monkeypatch.setattr(flow_setup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client)

    with pytest.raises(FlowSetupError) as exc_info:
        await update_appointment_flow_assets(db_session, tenant, account)

    assert exc_info.value.step == "publish_flow"
    assert len(fake_client.calls) == 2
    assert fake_client.calls[1]["url"].endswith("/APPT_FLOW_42/publish")


async def test_get_flow_validation_fails_precondition_without_flow_id(
    db_session: AsyncSession,
) -> None:
    tenant = await _seed_merchant_tenant(db_session, "No Flow For Validation")
    account = WhatsAppBusinessAccount(
        merchant_id=tenant.merchant_id, access_token_encrypted=encrypt("dummy-token")
    )
    db_session.add(account)
    await db_session.commit()

    with pytest.raises(FlowSetupError) as exc_info:
        await get_flow_validation(account)

    assert exc_info.value.step == "precondition"


async def test_get_flow_validation_returns_metas_response(
    db_session: AsyncSession, monkeypatch
) -> None:
    tenant = await _seed_merchant_tenant(db_session, "Validation Check")
    account = WhatsAppBusinessAccount(
        merchant_id=tenant.merchant_id,
        whatsapp_flow_id="FLOW_42",
        access_token_encrypted=encrypt("dummy-token"),
    )
    db_session.add(account)
    await db_session.commit()

    body = {
        "status": "PUBLISHED",
        "validation_errors": [],
        "health_status": {"can_send_message": "AVAILABLE"},
    }
    fake_client = _FakeAssetUploadClient(_FakeAssetUploadResponse(200, json_body=body))
    monkeypatch.setattr(flow_setup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client)

    result = await get_flow_validation(account)

    assert result == body
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["method"] == "get"
    assert fake_client.calls[0]["url"].endswith("/FLOW_42")
    assert fake_client.calls[0]["params"] == {"fields": "status,validation_errors,health_status"}


async def test_get_flow_validation_raises_on_failure(db_session: AsyncSession, monkeypatch) -> None:
    tenant = await _seed_merchant_tenant(db_session, "Validation Fails")
    account = WhatsAppBusinessAccount(
        merchant_id=tenant.merchant_id,
        whatsapp_flow_id="FLOW_42",
        access_token_encrypted=encrypt("dummy-token"),
    )
    db_session.add(account)
    await db_session.commit()

    fake_client = _FakeAssetUploadClient(_FakeAssetUploadResponse(400, "bad request"))
    monkeypatch.setattr(flow_setup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client)

    with pytest.raises(FlowSetupError) as exc_info:
        await get_flow_validation(account)

    assert exc_info.value.step == "get_flow_validation"


async def test_get_flow_validation_uses_explicit_flow_id_for_appointment_flow(
    db_session: AsyncSession, monkeypatch
) -> None:
    tenant = await _seed_merchant_tenant(db_session, "Appt Validation Check")
    account = WhatsAppBusinessAccount(
        merchant_id=tenant.merchant_id,
        whatsapp_flow_id="FLOW_42",
        whatsapp_appointment_flow_id="APPT_FLOW_42",
        access_token_encrypted=encrypt("dummy-token"),
    )
    db_session.add(account)
    await db_session.commit()

    body = {
        "status": "PUBLISHED",
        "validation_errors": [],
        "health_status": {"can_send_message": "AVAILABLE"},
    }
    fake_client = _FakeAssetUploadClient(_FakeAssetUploadResponse(200, json_body=body))
    monkeypatch.setattr(flow_setup_domain.httpx, "AsyncClient", lambda **kwargs: fake_client)

    result = await get_flow_validation(account, flow_id=account.whatsapp_appointment_flow_id)

    assert result == body
    assert len(fake_client.calls) == 1
    # Reads the appointment flow_id, not waba.whatsapp_flow_id (which is
    # also set here, to prove the explicit flow_id wins).
    assert fake_client.calls[0]["url"].endswith("/APPT_FLOW_42")


async def test_get_flow_validation_fails_precondition_when_appointment_flow_unset(
    db_session: AsyncSession,
) -> None:
    """Passing flow_id=account.whatsapp_appointment_flow_id explicitly still
    hits the precondition when that flow was never set up -- distinct from
    test_get_flow_validation_fails_precondition_without_flow_id, which
    exercises the *omitted* flow_id (defaulting to waba.whatsapp_flow_id)
    rather than an explicitly-passed one. waba.whatsapp_flow_id is
    deliberately left unset too here: since flow_id's default is plain
    `None`, an explicitly-passed None is indistinguishable from an omitted
    argument and *would* fall back to waba.whatsapp_flow_id if that were
    set (see get_flow_validation's docstring) -- leaving both unset is
    what isolates "the appointment flow specifically was never set up" as
    the actual failure this test is asserting."""
    tenant = await _seed_merchant_tenant(db_session, "No Appt Flow For Validation")
    account = WhatsAppBusinessAccount(
        merchant_id=tenant.merchant_id, access_token_encrypted=encrypt("dummy-token")
    )
    db_session.add(account)
    await db_session.commit()

    with pytest.raises(FlowSetupError) as exc_info:
        await get_flow_validation(account, flow_id=account.whatsapp_appointment_flow_id)

    assert exc_info.value.step == "precondition"
