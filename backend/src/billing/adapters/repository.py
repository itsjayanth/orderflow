import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from billing.domain.models import BillingEvent, Plan, Subscription
from shared.tenant import TenantContext


class PlanRepository:
    """Global reference data -- no TenantContext, same reasoning as the
    Plan model's own docstring."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, plan_id: uuid.UUID) -> Plan | None:
        return await self._session.get(Plan, plan_id)

    async def get_by_tier_and_interval(self, tier: str, billing_interval: str) -> Plan | None:
        result = await self._session.execute(
            select(Plan).where(Plan.tier == tier, Plan.billing_interval == billing_interval)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Plan]:
        result = await self._session.execute(select(Plan).order_by(Plan.price_inr))
        return list(result.scalars().all())


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, tenant: TenantContext) -> Subscription | None:
        return await self._session.get(Subscription, tenant.merchant_id)

    async def create(
        self,
        tenant: TenantContext,
        *,
        plan_id: uuid.UUID,
        status: str,
        trial_ends_at: datetime.datetime | None,
    ) -> Subscription:
        subscription = Subscription(
            merchant_id=tenant.merchant_id,
            plan_id=plan_id,
            status=status,
            trial_ends_at=trial_ends_at,
        )
        self._session.add(subscription)
        await self._session.flush()
        return subscription

    async def save(self, subscription: Subscription) -> Subscription:
        """Persists mutations already applied in-place (e.g. by
        transition_subscription_status) -- the session already tracks the
        entity, so this is just an explicit flush point, same convention
        as MerchantPaymentCredentialsRepository.upsert's ending flush."""
        await self._session.flush()
        return subscription

    async def get_by_provider_subscription_id(
        self, provider_subscription_id: str
    ) -> Subscription | None:
        """Not tenant-scoped -- the webhook handler only has the
        provider's subscription id, not a resolved tenant, and the whole
        point is resolving the tenant FROM this id, never trusting a
        client-echoed merchant id. Same reasoning as
        payments/adapters/repository.py's
        PaymentEventRepository.get_latest_by_provider_order_id."""
        result = await self._session.execute(
            select(Subscription).where(
                Subscription.provider_subscription_id == provider_subscription_id
            )
        )
        return result.scalar_one_or_none()

    async def list_trials_expiring(self, before: datetime.datetime) -> list[Subscription]:
        """Cross-tenant on purpose -- the trial-expiry sweep
        (shared/scheduler.py) is a system-level maintenance job, not a
        per-merchant dashboard query, the one legitimate exception to
        every other method here taking a TenantContext (same precedent as
        orders/adapters/repository.py's list_stale_awaiting_payment)."""
        result = await self._session.execute(
            select(Subscription).where(
                Subscription.status == "trialing",
                Subscription.trial_ends_at.is_not(None),
                Subscription.trial_ends_at <= before,
            )
        )
        return list(result.scalars().all())

    async def list_past_due_exceeding_grace(self, before: datetime.datetime) -> list[Subscription]:
        """Cross-tenant on purpose, same justification as
        list_trials_expiring above -- sweep-job only. `before` is compared
        against `past_due_since` (i.e. "went past_due before this
        instant"), not the current time."""
        result = await self._session.execute(
            select(Subscription).where(
                Subscription.status == "past_due",
                Subscription.past_due_since.is_not(None),
                Subscription.past_due_since <= before,
            )
        )
        return list(result.scalars().all())


class BillingEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_provider_payment_id(self, provider_payment_id: str) -> BillingEvent | None:
        result = await self._session.execute(
            select(BillingEvent).where(BillingEvent.provider_payment_id == provider_payment_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_by_provider_subscription_id(
        self, provider_subscription_id: str
    ) -> BillingEvent | None:
        result = await self._session.execute(
            select(BillingEvent)
            .where(BillingEvent.provider_subscription_id == provider_subscription_id)
            .order_by(BillingEvent.received_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        merchant_id: uuid.UUID,
        provider: str,
        event_type: str,
        provider_payment_id: str | None = None,
        provider_subscription_id: str | None = None,
        raw_payload: str | None = None,
    ) -> BillingEvent:
        event = BillingEvent(
            merchant_id=merchant_id,
            provider=provider,
            event_type=event_type,
            provider_payment_id=provider_payment_id,
            provider_subscription_id=provider_subscription_id,
            raw_payload=raw_payload,
        )
        self._session.add(event)
        await self._session.flush()
        return event
