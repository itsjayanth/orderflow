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

    async def upsert_from_embedded_signup(
        self,
        tenant: TenantContext,
        *,
        meta_waba_id: str,
        phone_number_id: str | None,
        display_phone_number: str | None,
        access_token_encrypted: str,
        registration_pin_encrypted: str | None,
    ) -> WhatsAppBusinessAccount:
        """Same idea as upsert() (the manual-entry path), but also records
        meta_waba_id and registration_pin_encrypted, which the manual form
        never captures -- see onboarding/domain/embedded_signup.py.
        connection_status/webhook_subscribed intentionally are NOT set to
        "connected"/True here the way upsert() unconditionally does:
        embedded_signup.py sets webhook_subscribed only after the WABA
        subscription call actually succeeds, so this only persists what's
        verified to exist so far (a real token, tied to a real WABA)."""
        account = await self.get(tenant)
        if account is None:
            account = WhatsAppBusinessAccount(merchant_id=tenant.merchant_id)
            self._session.add(account)

        account.meta_waba_id = meta_waba_id
        if phone_number_id is not None:
            account.phone_number_id = phone_number_id
        if display_phone_number is not None:
            account.display_phone_number = display_phone_number
        account.access_token_encrypted = access_token_encrypted
        if registration_pin_encrypted is not None:
            account.registration_pin_encrypted = registration_pin_encrypted
        account.connection_status = "connected"
        if account.connected_at is None:
            account.connected_at = datetime.datetime.now(datetime.UTC)

        await self._session.flush()
        return account

    async def mark_webhook_subscribed(self, tenant: TenantContext) -> None:
        account = await self.get(tenant)
        if account is not None:
            account.webhook_subscribed = True
            await self._session.flush()

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

    async def set_flow_private_key(
        self, tenant: TenantContext, *, private_key_encrypted: str
    ) -> WhatsAppBusinessAccount:
        """Persists just the (shared, business-level) RSA private key --
        called the moment its matching public half is confirmed uploaded
        to Meta, *before* attempting to create a Flow object against it.
        Splitting this out from set_flow_credentials/
        set_appointment_flow_credentials closes a real gap that bit a live
        merchant: uploading the public key and then failing to create the
        Flow (e.g. Meta rejecting the create_flow call) used to leave the
        newly-rotated public key live at Meta with no matching private key
        ever saved here, since the old code only persisted the key
        alongside a successful flow_id -- breaking decryption for every
        Flow this merchant has (they share one key pair), not just the one
        being set up. Now the key is safe on file the instant it's live,
        independent of whether Flow creation goes on to succeed."""
        account = await self.get(tenant)
        if account is None:
            raise ValueError(f"No WhatsAppBusinessAccount for merchant {tenant.merchant_id}")

        account.flow_private_key_encrypted = private_key_encrypted
        await self._session.flush()
        return account

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

    async def update_messaging_tier_daily_limit(
        self, tenant: TenantContext, *, messaging_tier_daily_limit: int
    ) -> WhatsAppBusinessAccount | None:
        account = await self.get(tenant)
        if account is None:
            return None
        account.messaging_tier_daily_limit = messaging_tier_daily_limit
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
