import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from flows.domain import setup as flow_setup_domain
from flows.domain.setup import FlowSetupError, setup_whatsapp_flow, update_flow_assets
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
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


class _FakeAssetUploadClient:
    """Records every POST made against it -- lets a test assert
    update_flow_assets hits the right Meta endpoint with the right
    flow_id, without a real network call."""

    def __init__(self, response: _FakeAssetUploadResponse) -> None:
        self.calls: list[dict] = []
        self._response = response

    async def __aenter__(self) -> "_FakeAssetUploadClient":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def post(self, url: str, **kwargs: object) -> _FakeAssetUploadResponse:
        self.calls.append({"url": url, **kwargs})
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

    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["url"].endswith("/FLOW_42/assets")
    assert fake_client.calls[0]["data"] == {"name": "flow.json", "asset_type": "FLOW_JSON"}


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
