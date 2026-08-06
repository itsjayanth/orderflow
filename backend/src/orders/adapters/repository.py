import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from orders.domain.models import Order, OrderItem, OrderStatusEvent
from orders.domain.state_machine import transition_fulfillment_status
from shared.tenant import TenantContext


class OrderNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class OrderItemInput:
    menu_item_id: uuid.UUID
    name_snapshot: str
    price_snapshot: Decimal
    quantity: int


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        tenant: TenantContext,
        *,
        customer_id: uuid.UUID,
        order_type: str,
        payment_method: str,
        payment_status: str,
        items: list[OrderItemInput],
        fulfillment_status: str | None = None,
        delivery_address_id: uuid.UUID | None = None,
        whatsapp_conversation_ref: str | None = None,
    ) -> Order:
        """Not exposed via the API in this phase -- orders are only created
        by the payment flow (Phase 5) or the COD ordering flow (Phase 6).
        Exists so tests can seed valid orders directly, and so those later
        phases have a ready-made entry point that already snapshots items
        correctly."""
        order_items = [
            OrderItem(
                menu_item_id=item.menu_item_id,
                name_snapshot=item.name_snapshot,
                price_snapshot=item.price_snapshot,
                quantity=item.quantity,
                line_total=item.price_snapshot * item.quantity,
            )
            for item in items
        ]
        subtotal = sum((oi.line_total for oi in order_items), start=Decimal("0"))

        order = Order(
            merchant_id=tenant.merchant_id,
            customer_id=customer_id,
            order_type=order_type,
            delivery_address_id=delivery_address_id,
            payment_method=payment_method,
            payment_status=payment_status,
            fulfillment_status=fulfillment_status,
            subtotal=subtotal,
            total=subtotal,
            whatsapp_conversation_ref=whatsapp_conversation_ref,
            items=order_items,
        )
        self._session.add(order)
        await self._session.flush()
        return order

    async def get(self, tenant: TenantContext, order_id: uuid.UUID) -> Order | None:
        result = await self._session.execute(
            select(Order)
            .where(Order.order_id == order_id, Order.merchant_id == tenant.merchant_id)
            .options(selectinload(Order.items))
        )
        return result.scalar_one_or_none()

    async def list(
        self, tenant: TenantContext, fulfillment_status: str | None = None
    ) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.merchant_id == tenant.merchant_id)
            .options(selectinload(Order.items))
            .order_by(Order.placed_at.desc())
        )
        if fulfillment_status is not None:
            stmt = stmt.where(Order.fulfillment_status == fulfillment_status)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def transition_fulfillment_status(
        self,
        tenant: TenantContext,
        order_id: uuid.UUID,
        to_status: str,
        *,
        changed_by: str,
        notified_customer: bool = False,
    ) -> Order:
        """The only path that mutates fulfillment_status -- always goes
        through the domain state machine first (defense in depth: even a
        bug elsewhere in the app can't skip validation, since there's no
        other way to write this field)."""
        order = await self.get(tenant, order_id)
        if order is None:
            raise OrderNotFoundError(order_id)

        from_status = order.fulfillment_status
        transition_fulfillment_status(order, to_status)

        self._session.add(
            OrderStatusEvent(
                order_id=order.order_id,
                from_status=from_status,
                to_status=to_status,
                changed_by=changed_by,
                notified_customer=notified_customer,
            )
        )
        await self._session.flush()
        return order
