import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.domain.models import Item, MerchantItemCounter
from shared.tenant import TenantContext


class ItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _next_item_number(self, merchant_id: uuid.UUID) -> int:
        """Atomic per-merchant counter upsert -- see
        orders/adapters/repository.py's `_next_order_number` for the exact
        same pattern and why it's safe under concurrent creation."""
        stmt = (
            pg_insert(MerchantItemCounter)
            .values(merchant_id=merchant_id, next_item_number=2)
            .on_conflict_do_update(
                index_elements=[MerchantItemCounter.merchant_id],
                set_={
                    "next_item_number": (
                        MerchantItemCounter.__table__.c.next_item_number + 1
                    )
                },
            )
            .returning(MerchantItemCounter.next_item_number)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() - 1

    async def list(
        self,
        tenant: TenantContext,
        include_unavailable: bool = True,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Item]:
        """`limit`/`offset` are optional and offset-based (simpler than a
        created_at+item_id keyset cursor, and acceptable here since
        nothing yet drives repeat deep pagination -- the trade-off is that
        a page can skip or repeat a row if items are inserted/deleted
        between two calls, unlike a keyset cursor). Omitted (the default),
        behavior is exactly as before this pagination support was added:
        every matching row, unbounded -- this method has several other
        callers (onboarding, flows, conversation) that rely on that and
        never pass `limit`. When `limit` is given, `limit + 1` rows are
        fetched so the caller (catalog/api/router.py's list_items) can
        detect "is there another page" itself by checking whether more
        than `limit` rows came back, then trim to `limit` before
        returning to its own caller -- kept out of this method so its
        return type (and every existing call site) stays untouched."""
        stmt = select(Item).where(Item.merchant_id == tenant.merchant_id)
        if not include_unavailable:
            stmt = stmt.where(Item.is_available.is_(True))
        stmt = stmt.order_by(Item.created_at)
        if limit is not None:
            stmt = stmt.offset(offset).limit(limit + 1)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        tenant: TenantContext,
        category: str,
        name: str,
        price: Decimal,
        image_url: str | None = None,
    ) -> Item:
        item_number = await self._next_item_number(tenant.merchant_id)
        item = Item(
            merchant_id=tenant.merchant_id,
            item_number=item_number,
            category=category,
            name=name,
            price=price,
            image_url=image_url,
        )
        self._session.add(item)
        await self._session.flush()
        return item

    async def get(self, tenant: TenantContext, item_id: uuid.UUID) -> Item | None:
        item = await self._session.get(Item, item_id)
        if item is None or item.merchant_id != tenant.merchant_id:
            return None
        return item

    async def update(
        self,
        tenant: TenantContext,
        item_id: uuid.UUID,
        *,
        category: str | None = None,
        name: str | None = None,
        price: Decimal | None = None,
        is_available: bool | None = None,
        image_url: str | None = None,
    ) -> Item | None:
        item = await self.get(tenant, item_id)
        if item is None:
            return None

        if category is not None:
            item.category = category
        if name is not None:
            item.name = name
        if price is not None:
            item.price = price
        if is_available is not None:
            item.is_available = is_available
        if image_url is not None:
            item.image_url = image_url

        await self._session.flush()
        return item
