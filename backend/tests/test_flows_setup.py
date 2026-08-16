import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from flows.domain.setup import FlowSetupError, setup_whatsapp_flow
from identity.adapters.repository import MerchantRepository
from onboarding.domain.models import WhatsAppBusinessAccount
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
