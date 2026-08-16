import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from flows.domain.setup import FlowSetupError, setup_whatsapp_flow
from identity.adapters.repository import MerchantRepository
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from shared.tenant import TenantContext


async def test_setup_fails_precondition_without_credentials(db_session: AsyncSession) -> None:
    merchant = await MerchantRepository(db_session).create(
        business_name="No Creds Yet", owner_contact="nocreds@example.com"
    )
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    # No upsert() call -- get() on a merchant with no WABA row at all should
    # be handled by the caller (the API router 400s before calling in); here
    # we exercise the case where a row exists but is missing credentials.
    from onboarding.domain.models import WhatsAppBusinessAccount

    account = WhatsAppBusinessAccount(merchant_id=merchant.merchant_id)
    db_session.add(account)
    await db_session.commit()

    account = await WhatsAppBusinessAccountRepository(db_session).get(tenant)
    assert account is not None

    with pytest.raises(FlowSetupError) as exc_info:
        await setup_whatsapp_flow(
            db_session,
            tenant,
            account,
            meta_waba_id="123",
            backend_base_url="https://example.com",
        )

    assert exc_info.value.step == "precondition"
