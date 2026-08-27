import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from onboarding.domain.models import WhatsAppBusinessAccount
from shared.tenant import TenantContext


class WhatsAppBusinessAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, tenant: TenantContext) -> WhatsAppBusinessAccount | None:
        result = await self._session.execute(
            select(WhatsAppBusinessAccount).where(
                WhatsAppBusinessAccount.merchant_id == tenant.merchant_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_phone_number_id(self, phone_number_id: str) -> WhatsAppBusinessAccount | None:
        """Cross-tenant on purpose -- this is how the Conversation Handler
        resolves *which* merchant an inbound WhatsApp message belongs to
        (ARCHITECTURE.md Section 2/8), before any TenantContext exists."""
        result = await self._session.execute(
            select(WhatsAppBusinessAccount).where(
                WhatsAppBusinessAccount.phone_number_id == phone_number_id
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        tenant: TenantContext,
        *,
        phone_number_id: str,
        access_token_encrypted: str,
        display_phone_number: str | None = None,
    ) -> WhatsAppBusinessAccount:
        account = await self.get(tenant)
        if account is None:
            account = WhatsAppBusinessAccount(merchant_id=tenant.merchant_id)
            self._session.add(account)

        account.phone_number_id = phone_number_id
        account.access_token_encrypted = access_token_encrypted
        account.display_phone_number = display_phone_number
        account.connection_status = "connected"
        if account.connected_at is None:
            account.connected_at = datetime.datetime.now(datetime.UTC)

        await self._session.flush()
        return account

    async def get_by_flow_id(self, flow_id: str) -> WhatsAppBusinessAccount | None:
        """Cross-tenant on purpose, same reason as get_by_phone_number_id --
        flows/api/router.py's data-exchange endpoint doesn't have a
        TenantContext yet when Meta's request lands, only the flow_id in
        flow_token (see flows/domain/order_builder.py's FlowToken)."""
        result = await self._session.execute(
            select(WhatsAppBusinessAccount).where(
                WhatsAppBusinessAccount.whatsapp_flow_id == flow_id
            )
        )
        return result.scalar_one_or_none()

    async def set_flow_credentials(
        self, tenant: TenantContext, *, flow_id: str, private_key_encrypted: str
    ) -> WhatsAppBusinessAccount:
        """Called once by scripts/setup_whatsapp_flow.py after creating and
        publishing the Flow and uploading its public key to Meta."""
        account = await self.get(tenant)
        if account is None:
            raise ValueError(f"No WhatsAppBusinessAccount for merchant {tenant.merchant_id}")

        account.whatsapp_flow_id = flow_id
        account.flow_private_key_encrypted = private_key_encrypted
        await self._session.flush()
        return account

    async def set_appointment_flow_credentials(
        self, tenant: TenantContext, *, flow_id: str, private_key_encrypted: str
    ) -> WhatsAppBusinessAccount:
        """Called once by scripts/setup_whatsapp_appointment_flow.py after
        creating and publishing the appointment Flow and uploading its
        (shared, business-level) public key to Meta."""
        account = await self.get(tenant)
        if account is None:
            raise ValueError(f"No WhatsAppBusinessAccount for merchant {tenant.merchant_id}")

        account.whatsapp_appointment_flow_id = flow_id
        account.flow_private_key_encrypted = private_key_encrypted
        await self._session.flush()
        return account
