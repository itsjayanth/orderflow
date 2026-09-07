from fastapi import APIRouter, Header, HTTPException, Request, status

from billing.adapters.gateway_selector import REAL_KEY_PREFIXES, get_billing_gateway
from billing.adapters.repository import BillingEventRepository, SubscriptionRepository
from billing.domain.gateway import BillingWebhookVerificationError
from billing.domain.state_machine import IllegalTransitionError, transition_subscription_status
from shared.config import get_settings
from shared.deps import DbSession

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

# Maps Razorpay's raw Subscriptions webhook event names onto
# Subscription.status transitions -- see billing/domain/state_machine.py's
# SUBSCRIPTION_TRANSITIONS. An event type not in this table is still
# recorded as a BillingEvent audit row, just with no status transition
# attempted (e.g. subscription.updated, addon-related events).
_EVENT_TYPE_TO_STATUS = {
    "subscription.activated": "active",
    "subscription.charged": "active",
    "subscription.pending": "past_due",
    "payment.failed": "past_due",
    "subscription.halted": "canceled",
    "subscription.cancelled": "canceled",
}


def _is_real_platform_account() -> bool:
    key_id = get_settings().platform_razorpay_key_id
    return bool(key_id and key_id.startswith(REAL_KEY_PREFIXES))


@router.post("/webhook")
async def billing_webhook(
    request: Request,
    session: DbSession,
    x_razorpay_signature: str = Header(...),
) -> dict[str, str]:
    """Platform-billing counterpart to payments/api/router.py's
    razorpay_webhook -- public, signature-verified, no TenantContext up
    front (the tenant is resolved FROM the verified payload's
    provider_subscription_id, never trusted from the client). Exactly one
    platform Razorpay account backs every merchant, so credentials come
    from Settings, not a per-merchant credentials row."""
    body = await request.body()
    settings = get_settings()
    gateway = get_billing_gateway(
        settings.platform_razorpay_key_id,
        settings.platform_razorpay_key_secret,
        settings.platform_razorpay_webhook_secret,
    )

    try:
        verified = gateway.verify_webhook(payload=body, signature=x_razorpay_signature)
    except BillingWebhookVerificationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature") from exc

    billing_event_repo = BillingEventRepository(session)
    provider = "razorpay" if _is_real_platform_account() else "dummy"

    if verified.provider_payment_id is not None:
        already_processed = await billing_event_repo.get_by_provider_payment_id(
            verified.provider_payment_id
        )
        if already_processed is not None:
            await billing_event_repo.create(
                merchant_id=already_processed.merchant_id,
                provider=already_processed.provider,
                event_type="webhook_received_duplicate",
                provider_payment_id=verified.provider_payment_id,
                provider_subscription_id=verified.provider_subscription_id,
                raw_payload=body.decode("utf-8"),
            )
            await session.commit()
            return {"status": "duplicate"}

    subscription = await SubscriptionRepository(session).get_by_provider_subscription_id(
        verified.provider_subscription_id
    )
    if subscription is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No subscription found for this provider subscription id"
        )

    to_status = _EVENT_TYPE_TO_STATUS.get(verified.event_type)
    if to_status is not None:
        try:
            transition_subscription_status(subscription, to_status)
        except IllegalTransitionError:
            # e.g. a redelivered webhook for a subscription that's already
            # in (or past) the target state -- not an error, just nothing
            # left to do. Same "log as duplicate, don't raise" handling as
            # payments/api/router.py's already-settled-order branch.
            await billing_event_repo.create(
                merchant_id=subscription.merchant_id,
                provider=provider,
                event_type="webhook_received_duplicate",
                provider_payment_id=verified.provider_payment_id,
                provider_subscription_id=verified.provider_subscription_id,
                raw_payload=body.decode("utf-8"),
            )
            await session.commit()
            return {"status": "duplicate"}

    await billing_event_repo.create(
        merchant_id=subscription.merchant_id,
        provider=provider,
        event_type=verified.event_type,
        provider_payment_id=verified.provider_payment_id,
        provider_subscription_id=verified.provider_subscription_id,
        raw_payload=body.decode("utf-8"),
    )
    await session.commit()

    return {"status": "ok"}
