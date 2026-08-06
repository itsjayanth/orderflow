import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from payments.domain.models import MerchantPaymentCredentials, PaymentEvent
from shared.tenant import TenantContext


class MerchantPaymentCredentialsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, tenant: TenantContext) -> MerchantPaymentCredentials | None:
        return await self._session.get(MerchantPaymentCredentials, tenant.merchant_id)

    async def upsert(
        self, tenant: TenantContext, *, razorpay_key_id: str, razorpay_key_secret_encrypted: str
    ) -> MerchantPaymentCredentials:
        credentials = await self.get(tenant)
        if credentials is None:
            credentials = MerchantPaymentCredentials(merchant_id=tenant.merchant_id)
            self._session.add(credentials)

        credentials.razorpay_key_id = razorpay_key_id
        credentials.razorpay_key_secret_encrypted = razorpay_key_secret_encrypted

        await self._session.flush()
        return credentials


class PaymentEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_provider_payment_id(self, provider_payment_id: str) -> PaymentEvent | None:
        result = await self._session.execute(
            select(PaymentEvent).where(PaymentEvent.provider_payment_id == provider_payment_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_by_provider_order_id(self, provider_order_id: str) -> PaymentEvent | None:
        """Resolves which Order a webhook is for via the provider_order_id
        recorded at link-creation time -- per ARCHITECTURE.md Section 8,
        never from a tenant field the provider might echo back."""
        result = await self._session.execute(
            select(PaymentEvent)
            .where(PaymentEvent.provider_order_id == provider_order_id)
            .order_by(PaymentEvent.received_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        order_id: uuid.UUID,
        provider: str,
        event_type: str,
        provider_payment_id: str | None = None,
        provider_order_id: str | None = None,
        raw_payload: str | None = None,
        recorded_by: str = "system",
    ) -> PaymentEvent:
        event = PaymentEvent(
            order_id=order_id,
            provider=provider,
            event_type=event_type,
            provider_payment_id=provider_payment_id,
            provider_order_id=provider_order_id,
            raw_payload=raw_payload,
            recorded_by=recorded_by,
        )
        self._session.add(event)
        await self._session.flush()
        return event
