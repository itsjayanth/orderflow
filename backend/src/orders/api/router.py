import uuid

from fastapi import APIRouter, HTTPException, status

from orders.adapters.repository import OrderNotFoundError, OrderRepository
from orders.api.schemas import FulfillmentStatusUpdate, OrderOut
from orders.domain.events import OrderCompleted, OrderReady, publish
from orders.domain.state_machine import IllegalTransitionError
from shared.deps import CurrentStaffUserId, CurrentTenant, DbSession

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])

_EVENT_BY_STATUS = {
    "ready": OrderReady,
    "completed": OrderCompleted,
}


@router.get("", response_model=list[OrderOut])
async def list_orders(
    tenant: CurrentTenant,
    session: DbSession,
    fulfillment_status: str | None = None,
) -> list[OrderOut]:
    orders = await OrderRepository(session).list(tenant, fulfillment_status=fulfillment_status)
    return [OrderOut.model_validate(order) for order in orders]


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: uuid.UUID, tenant: CurrentTenant, session: DbSession) -> OrderOut:
    order = await OrderRepository(session).get(tenant, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return OrderOut.model_validate(order)


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

    return OrderOut.model_validate(order)
