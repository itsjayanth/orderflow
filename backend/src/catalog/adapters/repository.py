import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.domain.models import MenuItem, MerchantMenuItemCounter
from shared.tenant import TenantContext


class MenuItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _next_item_number(self, merchant_id: uuid.UUID) -> int:
        """Atomic per-merchant counter upsert -- see
        orders/adapters/repository.py's `_next_order_number` for the exact
        same pattern and why it's safe under concurrent creation."""
        stmt = (
            pg_insert(MerchantMenuItemCounter)
            .values(merchant_id=merchant_id, next_item_number=2)
            .on_conflict_do_update(
                index_elements=[MerchantMenuItemCounter.merchant_id],
                set_={
                    "next_item_number": (
                        MerchantMenuItemCounter.__table__.c.next_item_number + 1
                    )
                },
            )
            .returning(MerchantMenuItemCounter.next_item_number)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() - 1

    async def list(
        self, tenant: TenantContext, include_unavailable: bool = True
    ) -> list[MenuItem]:
        stmt = select(MenuItem).where(MenuItem.merchant_id == tenant.merchant_id)
        if not include_unavailable:
            stmt = stmt.where(MenuItem.is_available.is_(True))
        result = await self._session.execute(stmt.order_by(MenuItem.created_at))
        return list(result.scalars().all())

    async def create(
        self,
        tenant: TenantContext,
        category: str,
        name: str,
        price: Decimal,
        image_url: str | None = None,
    ) -> MenuItem:
        item_number = await self._next_item_number(tenant.merchant_id)
        menu_item = MenuItem(
            merchant_id=tenant.merchant_id,
            item_number=item_number,
            category=category,
            name=name,
            price=price,
            image_url=image_url,
        )
        self._session.add(menu_item)
        await self._session.flush()
        return menu_item

    async def get(self, tenant: TenantContext, menu_item_id: uuid.UUID) -> MenuItem | None:
        menu_item = await self._session.get(MenuItem, menu_item_id)
        if menu_item is None or menu_item.merchant_id != tenant.merchant_id:
            return None
        return menu_item

    async def update(
        self,
        tenant: TenantContext,
        menu_item_id: uuid.UUID,
        *,
        category: str | None = None,
        name: str | None = None,
        price: Decimal | None = None,
        is_available: bool | None = None,
        image_url: str | None = None,
    ) -> MenuItem | None:
        menu_item = await self.get(tenant, menu_item_id)
        if menu_item is None:
            return None

        if category is not None:
            menu_item.category = category
        if name is not None:
            menu_item.name = name
        if price is not None:
            menu_item.price = price
        if is_available is not None:
            menu_item.is_available = is_available
        if image_url is not None:
            menu_item.image_url = image_url

        await self._session.flush()
        return menu_item
