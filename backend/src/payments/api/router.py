import uuid

from fastapi import APIRouter, Header, HTTPException, Request, status

from appointments.adapters.repository import AppointmentNotFoundError, AppointmentRepository
from orders.adapters.repository import OrderNotFoundError, OrderRepository
from orders.domain.events import OrderPaid, publish
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

    # Order Service owns the actual lookup-with-lock + state-machine
    # transition (ARCHITECTURE.md Section 3: "Payment Service ... emits
    # the fact, Order Service reacts") -- this just resolves *which* order
    # (payments' own PaymentEvent lookup above) and hands it the verified
    # outcome. See OrderRepository.apply_payment_webhook_result's docstring
    # for the row-locking/duplicate-detection details.
    try:
        result = await OrderRepository(session).apply_payment_webhook_result(
            tenant, link_event.order_id, succeeded=verified.succeeded
        )
    except OrderNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found") from exc

    if result.duplicate:
        # e.g. a redelivered webhook for an order that already settled --
        # not an error, just nothing left to do.
        await payment_event_repo.create(
            order_id=result.order.order_id,
            provider=link_event.provider,
            event_type="webhook_received_duplicate",
            provider_payment_id=verified.provider_payment_id,
            provider_order_id=verified.provider_order_id,
        )
        await session.commit()
        return {"status": "duplicate"}

    await payment_event_repo.create(
        order_id=result.order.order_id,
        provider=link_event.provider,
        event_type="payment_succeeded" if verified.succeeded else "payment_failed",
        provider_payment_id=verified.provider_payment_id,
        provider_order_id=verified.provider_order_id,
    )
    await session.commit()

    if verified.succeeded:
        await publish(OrderPaid(order_id=result.order.order_id, merchant_id=merchant_id))

    return {"status": "ok"}


@router.post("/razorpay/appointment/{merchant_id}")
async def razorpay_appointment_webhook(
    merchant_id: uuid.UUID,
    request: Request,
    session: DbSession,
    x_razorpay_signature: str = Header(...),
) -> dict[str, str]:
    """Mirrors razorpay_webhook above almost exactly, but resolves back to
    an Appointment instead of an Order, via
    AppointmentRepository.apply_payment_webhook_result (Appointment Service's
    own guarded payment_status setter -- see
    appointments/domain/state_machine.py's transition_payment_status --
    rather than the full FSM `status` goes through, since there's no
    product-defined state machine for appointment payments, just a
    settled/not-settled guard). Deliberately publishes no event: nothing
    subscribes to an appointment payment event today, so there's nothing to
    notify."""
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
            appointment_id=already_processed.appointment_id,
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
    if link_event is None or link_event.appointment_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No appointment found for this payment")

    # Appointment Service owns the actual lookup-with-lock + guarded write
    # (same "Payment emits, [owning service] reacts" boundary as the Order
    # webhook above) -- see
    # AppointmentRepository.apply_payment_webhook_result's docstring.
    try:
        result = await AppointmentRepository(session).apply_payment_webhook_result(
            tenant, link_event.appointment_id, succeeded=verified.succeeded
        )
    except AppointmentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found") from exc

    if result.duplicate:
        # Already settled -- a redelivered webhook, not an error, same
        # "nothing left to do" handling as the Order flow's duplicate
        # branch above.
        await payment_event_repo.create(
            appointment_id=result.appointment.appointment_id,
            provider=link_event.provider,
            event_type="webhook_received_duplicate",
            provider_payment_id=verified.provider_payment_id,
            provider_order_id=verified.provider_order_id,
        )
        await session.commit()
        return {"status": "duplicate"}

    await payment_event_repo.create(
        appointment_id=result.appointment.appointment_id,
        provider=link_event.provider,
        event_type="payment_succeeded" if verified.succeeded else "payment_failed",
        provider_payment_id=verified.provider_payment_id,
        provider_order_id=verified.provider_order_id,
    )
    await session.commit()

    return {"status": "ok"}
