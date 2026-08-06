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
