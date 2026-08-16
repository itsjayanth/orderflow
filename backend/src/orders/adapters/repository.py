import builtins
import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import ColumnElement, case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from orders.domain.models import MerchantOrderCounter, Order, OrderItem, OrderStatusEvent
from orders.domain.state_machine import transition_fulfillment_status
from shared.tenant import TenantContext


class OrderNotFoundError(Exception):
    pass


def _day_range_bounds(
    from_date: datetime.date | None, to_date: datetime.date | None
) -> tuple[datetime.datetime | None, datetime.datetime | None]:
    """Converts inclusive calendar-date bounds into the UTC datetime range
    used to filter `Order.placed_at` (stored as timezone-aware UTC). Both
    ends are optional and independent -- omitted means unbounded on that
    side, matching the pre-filtering "all-time" behavior exactly when both
    are omitted. `to_date` is treated as inclusive of the whole day, so it's
    converted to an exclusive upper bound at the start of the next day."""
    lower = (
        datetime.datetime.combine(from_date, datetime.time.min, tzinfo=datetime.UTC)
        if from_date is not None
        else None
    )
    upper = (
        datetime.datetime.combine(to_date, datetime.time.min, tzinfo=datetime.UTC)
        + datetime.timedelta(days=1)
        if to_date is not None
        else None
    )
    return lower, upper


@dataclass(frozen=True, slots=True)
class OrderItemInput:
    menu_item_id: uuid.UUID
    name_snapshot: str
    price_snapshot: Decimal
    quantity: int


@dataclass(frozen=True, slots=True)
class OrderSummary:
    total_orders: int
    revenue_generated: Decimal
    amount_collected: Decimal
    cod_orders: int
    new_orders: int
    preparing_orders: int
    ready_orders: int
    completed_orders: int
    cancelled_orders: int


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _next_order_number(self, merchant_id: uuid.UUID) -> int:
        """Atomically hands out the next per-merchant order_number via a
        single upsert -- safe under concurrent order creation without a
        separate SELECT ... FOR UPDATE round trip. The counter row stores
        the *next* number to assign; a fresh merchant gets an implicit
        starting value of 2 on first insert so `next_order_number - 1`
        (i.e. 1) is what's returned and assigned to their first order."""
        stmt = (
            pg_insert(MerchantOrderCounter)
            .values(merchant_id=merchant_id, next_order_number=2)
            .on_conflict_do_update(
                index_elements=[MerchantOrderCounter.merchant_id],
                set_={
                    "next_order_number": MerchantOrderCounter.__table__.c.next_order_number + 1
                },
            )
            .returning(MerchantOrderCounter.next_order_number)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() - 1

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
        contact_phone: str | None = None,
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
        order_number = await self._next_order_number(tenant.merchant_id)

        order = Order(
            merchant_id=tenant.merchant_id,
            order_number=order_number,
            customer_id=customer_id,
            order_type=order_type,
            delivery_address_id=delivery_address_id,
            payment_method=payment_method,
            payment_status=payment_status,
            fulfillment_status=fulfillment_status,
            subtotal=subtotal,
            total=subtotal,
            whatsapp_conversation_ref=whatsapp_conversation_ref,
            contact_phone=contact_phone,
            items=order_items,
        )
        self._session.add(order)
        await self._session.flush()
        return order

    async def get(self, tenant: TenantContext, order_id: uuid.UUID) -> Order | None:
        result = await self._session.execute(
            select(Order)
            .where(Order.order_id == order_id, Order.merchant_id == tenant.merchant_id)
            .options(selectinload(Order.items), selectinload(Order.customer))
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        tenant: TenantContext,
        fulfillment_status: str | None = None,
        from_date: datetime.date | None = None,
        to_date: datetime.date | None = None,
    ) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.merchant_id == tenant.merchant_id)
            .options(selectinload(Order.items), selectinload(Order.customer))
            .order_by(Order.placed_at.desc())
        )
        if fulfillment_status is not None:
            stmt = stmt.where(Order.fulfillment_status == fulfillment_status)
        lower, upper = _day_range_bounds(from_date, to_date)
        if lower is not None:
            stmt = stmt.where(Order.placed_at >= lower)
        if upper is not None:
            stmt = stmt.where(Order.placed_at < upper)
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

    async def list_for_customer(
        self, tenant: TenantContext, customer_id: uuid.UUID, limit: int = 10
    ) -> builtins.list[Order]:
        result = await self._session.execute(
            select(Order)
            .where(Order.merchant_id == tenant.merchant_id, Order.customer_id == customer_id)
            .options(selectinload(Order.items))
            .order_by(Order.placed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_summary(
        self,
        tenant: TenantContext,
        from_date: datetime.date | None = None,
        to_date: datetime.date | None = None,
    ) -> OrderSummary:
        """One aggregate query for the dashboard's summary cards -- avoids
        loading every Order row (with items) into Python just to count/sum
        them. "revenue_generated" excludes cancelled orders (never real
        revenue); "amount_collected" is narrower still -- only orders whose
        payment_status shows money actually in hand (paid online, or COD
        marked collected), not merely placed. `from_date`/`to_date` are both
        optional and filter by `placed_at`; omitting both preserves the
        original all-time aggregate exactly."""

        def _sum_when(condition: ColumnElement[bool]) -> ColumnElement[Decimal]:
            return func.coalesce(func.sum(case((condition, Order.total), else_=0)), 0)

        def _count_when(condition: ColumnElement[bool]) -> ColumnElement[int]:
            return func.count(case((condition, 1), else_=None))

        not_cancelled = Order.fulfillment_status != "cancelled"
        collected = Order.payment_status.in_(("paid", "cod_collected"))

        stmt = select(
            func.count(),
            _sum_when(not_cancelled),
            _sum_when(collected),
            _count_when(Order.payment_method == "cod"),
            _count_when(Order.fulfillment_status == "new"),
            _count_when(Order.fulfillment_status == "preparing"),
            _count_when(Order.fulfillment_status == "ready"),
            _count_when(Order.fulfillment_status == "completed"),
            _count_when(Order.fulfillment_status == "cancelled"),
        ).where(Order.merchant_id == tenant.merchant_id)

        lower, upper = _day_range_bounds(from_date, to_date)
        if lower is not None:
            stmt = stmt.where(Order.placed_at >= lower)
        if upper is not None:
            stmt = stmt.where(Order.placed_at < upper)

        row = (await self._session.execute(stmt)).one()
        return OrderSummary(
            total_orders=row[0],
            revenue_generated=row[1],
            amount_collected=row[2],
            cod_orders=row[3],
            new_orders=row[4],
            preparing_orders=row[5],
            ready_orders=row[6],
            completed_orders=row[7],
            cancelled_orders=row[8],
        )

    async def list_stale_awaiting_payment(
        self, older_than: datetime.datetime
    ) -> builtins.list[Order]:
        """Cross-tenant on purpose -- the abandoned-order timeout sweep
        (shared/scheduler.py) is a system-level maintenance job, not a
        per-merchant dashboard query, so it's the one legitimate exception
        to every other method here taking a TenantContext."""
        result = await self._session.execute(
            select(Order).where(
                Order.payment_status == "awaiting_payment", Order.placed_at < older_than
            )
        )
        return list(result.scalars().all())
