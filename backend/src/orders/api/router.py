import datetime
import uuid

from fastapi import APIRouter, HTTPException, status

from customers.api.schemas import AddressOut
from orders.adapters.repository import OrderNotFoundError, OrderRepository
from orders.api.schemas import (
    FulfillmentStatusUpdate,
    OrderDetailOut,
    OrderItemOut,
    OrderOut,
    OrderSummaryOut,
    OrderUpdate,
)
from orders.domain.events import OrderCompleted, OrderProcessing, OrderReady, publish
from orders.domain.models import Order
from orders.domain.state_machine import IllegalTransitionError
from payments.adapters.repository import PaymentEventRepository
from shared.deps import CurrentStaffUserId, CurrentTenant, DbSession

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])

_EVENT_BY_STATUS = {
    "processing": OrderProcessing,
    "ready": OrderReady,
    "completed": OrderCompleted,
}


def _to_order_out(order: Order) -> OrderOut:
    """Built manually (rather than pure `OrderOut.model_validate(order,
    from_attributes=True)`) because customer_name/customer_whatsapp_number
    are flattened from the eager-loaded `order.customer` relationship, not
    plain attributes on Order itself."""
    return OrderOut(
        order_id=order.order_id,
        order_number=order.order_number,
        customer_id=order.customer_id,
        customer_number=order.customer.customer_number,
        customer_name=order.customer.display_name,
        customer_whatsapp_number=order.customer.whatsapp_number,
        order_type=order.order_type,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        fulfillment_status=order.fulfillment_status,
        contact_phone=order.contact_phone,
        notes=order.notes,
        subtotal=order.subtotal,
        total=order.total,
        currency=order.currency,
        placed_at=order.placed_at,
        paid_at=order.paid_at,
        ready_at=order.ready_at,
        completed_at=order.completed_at,
        items=[OrderItemOut.model_validate(item) for item in order.items],
    )


def _to_order_detail_out(order: Order) -> OrderDetailOut:
    return OrderDetailOut(
        **_to_order_out(order).model_dump(),
        delivery_address=AddressOut.model_validate(order.delivery_address)
        if order.delivery_address is not None
        else None,
    )


@router.get("", response_model=list[OrderOut])
async def list_orders(
    tenant: CurrentTenant,
    session: DbSession,
    fulfillment_status: str | None = None,
    from_date: datetime.date | None = None,
    to_date: datetime.date | None = None,
    customer_id: uuid.UUID | None = None,
) -> list[OrderOut]:
    orders = await OrderRepository(session).list(
        tenant,
        fulfillment_status=fulfillment_status,
        from_date=from_date,
        to_date=to_date,
        customer_id=customer_id,
    )
    return [_to_order_out(order) for order in orders]


@router.get("/summary", response_model=OrderSummaryOut)
async def get_order_summary(
    tenant: CurrentTenant,
    session: DbSession,
    from_date: datetime.date | None = None,
    to_date: datetime.date | None = None,
) -> OrderSummaryOut:
    # Must stay above /{order_id} -- FastAPI matches routes in declaration
    # order, and a UUID path converter would otherwise swallow "summary".
    summary = await OrderRepository(session).get_summary(
        tenant, from_date=from_date, to_date=to_date
    )
    return OrderSummaryOut(
        total_orders=summary.total_orders,
        revenue_generated=summary.revenue_generated,
        amount_collected=summary.amount_collected,
        cod_orders=summary.cod_orders,
        new_orders=summary.new_orders,
        processing_orders=summary.processing_orders,
        ready_orders=summary.ready_orders,
        completed_orders=summary.completed_orders,
        cancelled_orders=summary.cancelled_orders,
    )


@router.get("/{order_id}", response_model=OrderDetailOut)
async def get_order(
    order_id: uuid.UUID, tenant: CurrentTenant, session: DbSession
) -> OrderDetailOut:
    order = await OrderRepository(session).get(tenant, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return _to_order_detail_out(order)


@router.patch("/{order_id}/fulfillment-status", response_model=OrderOut)
async def update_fulfillment_status(
    order_id: uuid.UUID,
    body: FulfillmentStatusUpdate,
    tenant: CurrentTenant,
    staff_user_id: CurrentStaffUserId,
    session: DbSession,
) -> OrderOut:
    repo = OrderRepository(session)
    try:
        order = await repo.transition_fulfillment_status(
            tenant, order_id, body.to_status, changed_by=str(staff_user_id)
        )
    except OrderNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found") from exc
    except IllegalTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await session.commit()

    event_cls = _EVENT_BY_STATUS.get(body.to_status)
    if event_cls is not None:
        await publish(event_cls(order_id=order.order_id, merchant_id=tenant.merchant_id))

    return _to_order_out(order)


@router.patch("/{order_id}", response_model=OrderOut)
async def update_order(
    order_id: uuid.UUID, body: OrderUpdate, tenant: CurrentTenant, session: DbSession
) -> OrderOut:
    """Dashboard order-detail edit -- deliberately narrow (contact_phone and
    notes only): items/pricing are frozen snapshots by design
    (ARCHITECTURE.md Section 4), and payment/fulfillment_status each have
    their own state-machine-guarded endpoints below/above."""
    order = await OrderRepository(session).update_details(
        tenant, order_id, **body.model_dump(exclude_unset=True)
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    await session.commit()
    return _to_order_out(order)


@router.post("/{order_id}/collect-cod-payment", response_model=OrderOut)
async def collect_cod_payment(
    order_id: uuid.UUID,
    tenant: CurrentTenant,
    staff_user_id: CurrentStaffUserId,
    session: DbSession,
) -> OrderOut:
    """Fills the previously-unreachable cod_pending -> cod_collected gap
    (see orders/domain/state_machine.py) -- a staff member confirming cash
    was actually collected on delivery/pickup. Rejects (409) for any order
    not currently cod_pending, including online-paid orders, since that
    pair isn't in PAYMENT_TRANSITIONS."""
    repo = OrderRepository(session)
    try:
        order = await repo.transition_payment_status(tenant, order_id, "cod_collected")
    except OrderNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found") from exc
    except IllegalTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await PaymentEventRepository(session).create(
        order_id=order.order_id,
        provider="cod",
        event_type="cod_collected",
        recorded_by=str(staff_user_id),
    )
    await session.commit()
    return _to_order_out(order)
