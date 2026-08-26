import uuid

from fastapi import APIRouter, HTTPException, status

from catalog.adapters.repository import ItemRepository
from catalog.api.schemas import ItemCreate, ItemOut, ItemUpdate
from onboarding.domain.onboarding_service import try_advance_for_catalog_ready
from shared.deps import CurrentTenant, DbSession

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.get("/items", response_model=list[ItemOut])
async def list_items(tenant: CurrentTenant, session: DbSession) -> list[ItemOut]:
    items = await ItemRepository(session).list(tenant)
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
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    # Covers the case where the gate is only met by un-hiding an existing
    # item (is_available: true) rather than creating a new one.
    await try_advance_for_catalog_ready(session, tenant)
    await session.commit()
    return ItemOut.model_validate(item)
