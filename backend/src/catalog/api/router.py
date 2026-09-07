import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from catalog.adapters.repository import ItemRepository
from catalog.api.schemas import ItemCreate, ItemOut, ItemUpdate
from onboarding.domain.onboarding_service import try_advance_for_catalog_ready
from shared.deps import CurrentTenant, DbSession

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.get("/items", response_model=list[ItemOut])
async def list_items(
    tenant: CurrentTenant,
    session: DbSession,
    response: Response,
    limit: int | None = Query(default=None, gt=0, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ItemOut]:
    """`limit`/`offset` optional, off by default -- see list_orders in
    orders/api/router.py for the full rationale (bare-list body preserved
    for the existing frontend/tests, "more available" signalled via the
    X-Has-More header instead of an envelope)."""
    items = await ItemRepository(session).list(tenant, limit=limit, offset=offset)
    has_more = limit is not None and len(items) > limit
    if has_more:
        items = items[:limit]
    response.headers["X-Has-More"] = "true" if has_more else "false"
    return [ItemOut.model_validate(item) for item in items]


@router.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create_item(
    body: ItemCreate, tenant: CurrentTenant, session: DbSession
) -> ItemOut:
    item = await ItemRepository(session).create(
        tenant, category=body.category, name=body.name, price=body.price, image_url=body.image_url
    )
    # A new item is available by default, so this is the most common way the
    # onboarding catalog_ready gate (ARCHITECTURE.md Section 5) gets met.
    await try_advance_for_catalog_ready(session, tenant)
    await session.commit()
    return ItemOut.model_validate(item)


@router.patch("/items/{item_id}", response_model=ItemOut)
async def update_item(
    item_id: uuid.UUID, body: ItemUpdate, tenant: CurrentTenant, session: DbSession
) -> ItemOut:
    item = await ItemRepository(session).update(
        tenant, item_id, **body.model_dump(exclude_unset=True)
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    # Covers the case where the gate is only met by un-hiding an existing
    # item (is_available: true) rather than creating a new one.
    await try_advance_for_catalog_ready(session, tenant)
    await session.commit()
    return ItemOut.model_validate(item)
