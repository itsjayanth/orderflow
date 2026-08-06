import uuid

from fastapi import APIRouter, HTTPException, status

from catalog.adapters.repository import MenuItemRepository
from catalog.api.schemas import MenuItemCreate, MenuItemOut, MenuItemUpdate
from onboarding.domain.onboarding_service import try_advance_for_catalog_ready
from shared.deps import CurrentTenant, DbSession

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.get("/items", response_model=list[MenuItemOut])
async def list_items(tenant: CurrentTenant, session: DbSession) -> list[MenuItemOut]:
    items = await MenuItemRepository(session).list(tenant)
    return [MenuItemOut.model_validate(item) for item in items]


@router.post("/items", response_model=MenuItemOut, status_code=status.HTTP_201_CREATED)
async def create_item(
    body: MenuItemCreate, tenant: CurrentTenant, session: DbSession
) -> MenuItemOut:
    item = await MenuItemRepository(session).create(
        tenant, category=body.category, name=body.name, price=body.price
    )
    # A new item is available by default, so this is the most common way the
    # onboarding catalog_ready gate (ARCHITECTURE.md Section 5) gets met.
    await try_advance_for_catalog_ready(session, tenant)
    await session.commit()
    return MenuItemOut.model_validate(item)


@router.patch("/items/{menu_item_id}", response_model=MenuItemOut)
async def update_item(
    menu_item_id: uuid.UUID, body: MenuItemUpdate, tenant: CurrentTenant, session: DbSession
) -> MenuItemOut:
    item = await MenuItemRepository(session).update(
        tenant, menu_item_id, **body.model_dump(exclude_unset=True)
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    # Covers the case where the gate is only met by un-hiding an existing
    # item (is_available: true) rather than creating a new one.
    await try_advance_for_catalog_ready(session, tenant)
    await session.commit()
    return MenuItemOut.model_validate(item)
