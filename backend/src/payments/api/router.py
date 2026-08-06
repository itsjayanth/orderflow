import uuid

from fastapi import APIRouter, Header, HTTPException, Request, status

from orders.adapters.repository import OrderRepository
from orders.domain.events import OrderPaid, publish
from orders.domain.state_machine import IllegalTransitionError, transition_payment_status
from payments.adapters.gateway_selector import get_payment_gateway, resolve_credentials
from payments.adapters.repository import (
    MerchantPaymentCredentialsRepository,
    PaymentEventRepository,
)
from payments.domain.gateway import WebhookVerificationError
from shared.deps import DbSession
from shared.tenant import TenantContext

router = APIRouter(prefix="/api/v1/payments/webhook", tags=["payments"])


@router.post("/razorpay/{merchant_id}")
async def razorpay_webhook(
    merchant_id: uuid.UUID,
    request: Request,
    session: DbSession,
    x_razorpay_signature: str = Header(...),
) -> dict[str, str]:
    body = await request.body()
    tenant = TenantContext(merchant_id=merchant_id)

    credentials = await MerchantPaymentCredentialsRepository(session).get(tenant)
    key_id, key_secret = resolve_credentials(credentials, merchant_id)
    gateway = get_payment_gateway(key_id, key_secret)

    try:
        verified = gateway.verify_webhook(payload=body, signature=x_razorpay_signature)
    except WebhookVerificationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature") from exc

    payment_event_repo = PaymentEventRepository(session)

    already_processed = await payment_event_repo.get_by_provider_payment_id(
        verified.provider_payment_id
    )
    if already_processed is not None:
        await payment_event_repo.create(
            order_id=already_processed.order_id,
            provider=already_processed.provider,
            event_type="webhook_received_duplicate",
            provider_payment_id=verified.provider_payment_id,
            provider_order_id=verified.provider_order_id,
        )
        await session.commit()
        return {"status": "duplicate"}

    link_event = await payment_event_repo.get_latest_by_provider_order_id(
        verified.provider_order_id
    )
    if link_event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No order found for this payment")

    order = await OrderRepository(session).get(tenant, link_event.order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")

    to_status = "paid" if verified.succeeded else "payment_failed"
    try:
        transition_payment_status(order, to_status)
    except IllegalTransitionError:
        # e.g. a redelivered webhook for an order that already settled --
        # not an error, just nothing left to do.
        await payment_event_repo.create(
            order_id=order.order_id,
            provider=link_event.provider,
            event_type="webhook_received_duplicate",
            provider_payment_id=verified.provider_payment_id,
            provider_order_id=verified.provider_order_id,
        )
        await session.commit()
        return {"status": "duplicate"}

    await payment_event_repo.create(
        order_id=order.order_id,
        provider=link_event.provider,
        event_type="payment_succeeded" if verified.succeeded else "payment_failed",
        provider_payment_id=verified.provider_payment_id,
        provider_order_id=verified.provider_order_id,
    )
    await session.commit()

    if verified.succeeded:
        await publish(OrderPaid(order_id=order.order_id, merchant_id=merchant_id))

    return {"status": "ok"}
