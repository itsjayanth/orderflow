import datetime
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import MenuItemRepository
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from orders.adapters.repository import OrderItemInput, OrderRepository
from shared.scheduler import sweep_abandoned_orders
from shared.tenant import TenantContext


async def _make_tenant(db_session: AsyncSession) -> TenantContext:
    merchant = await MerchantRepository(db_session).create(
        business_name="Sweep Kitchen", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    return TenantContext(merchant_id=merchant.merchant_id)


async def test_sweep_cancels_abandoned_orders_but_not_recent_ones(
    db_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(db_session)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    menu_item = await MenuItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    order_repo = OrderRepository(db_session)

    def _items() -> list[OrderItemInput]:
        return [
            OrderItemInput(
                menu_item_id=menu_item.menu_item_id,
                name_snapshot=menu_item.name,
                price_snapshot=menu_item.price,
                quantity=1,
            )
        ]

    stale_order = await order_repo.create(
        tenant,
        customer_id=customer.customer_id,
        order_type="pickup",
        payment_method="online",
        payment_status="awaiting_payment",
        items=_items(),
    )
    recent_order = await order_repo.create(
        tenant,
        customer_id=customer.customer_id,
        order_type="pickup",
        payment_method="online",
        payment_status="awaiting_payment",
        items=_items(),
    )
    # Backdate only the stale order's placed_at directly (bypassing the
    # domain layer, which has no reason to ever set this after creation).
    stale_order.placed_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=2)
    await db_session.commit()

    await sweep_abandoned_orders()

    await db_session.refresh(stale_order)
    await db_session.refresh(recent_order)
    assert stale_order.payment_status == "cancelled"
    assert stale_order.fulfillment_status == "cancelled"
    assert recent_order.payment_status == "awaiting_payment"
