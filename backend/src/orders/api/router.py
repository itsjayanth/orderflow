import datetime
import uuid

from fastapi import APIRouter, HTTPException, status

from orders.adapters.repository import OrderNotFoundError, OrderRepository
from orders.api.schemas import FulfillmentStatusUpdate, OrderItemOut, OrderOut, OrderSummaryOut
from orders.domain.events import OrderCompleted, OrderPreparing, OrderReady, publish
from orders.domain.models import Order
from orders.domain.state_machine import IllegalTransitionError
from shared.deps import CurrentStaffUserId, CurrentTenant, DbSession

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])

_EVENT_BY_STATUS = {
    "preparing": OrderPreparing,
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
        subtotal=order.subtotal,
        total=order.total,
        currency=order.currency,
        placed_at=order.placed_at,
        paid_at=order.paid_at,
        ready_at=order.ready_at,
        completed_at=order.completed_at,
        items=[OrderItemOut.model_validate(item) for item in order.items],
    )


@router.get("", response_model=list[OrderOut])
async def list_orders(
    tenant: CurrentTenant,
    session: DbSession,
    fulfillment_status: str | None = None,
    from_date: datetime.date | None = None,
    to_date: datetime.date | None = None,
) -> list[OrderOut]:
    orders = await OrderRepository(session).list(
        tenant, fulfillment_status=fulfillment_status, from_date=from_date, to_date=to_date
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
        preparing_orders=summary.preparing_orders,
        ready_orders=summary.ready_orders,
        completed_orders=summary.completed_orders,
        cancelled_orders=summary.cancelled_orders,
    )


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: uuid.UUID, tenant: CurrentTenant, session: DbSession) -> OrderOut:
    order = await OrderRepository(session).get(tenant, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return _to_order_out(order)


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
