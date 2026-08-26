import uuid

from fastapi import APIRouter, HTTPException, status

from faq.adapters.repository import FAQItemRepository
from faq.api.schemas import FAQItemCreate, FAQItemOut, FAQItemUpdate
from shared.deps import CurrentTenant, DbSession

router = APIRouter(prefix="/api/v1/faq", tags=["faq"])


@router.get("/items", response_model=list[FAQItemOut])
async def list_items(tenant: CurrentTenant, session: DbSession) -> list[FAQItemOut]:
    items = await FAQItemRepository(session).list(tenant)
    return [FAQItemOut.model_validate(item) for item in items]


@router.post("/items", response_model=FAQItemOut, status_code=status.HTTP_201_CREATED)
async def create_item(body: FAQItemCreate, tenant: CurrentTenant, session: DbSession) -> FAQItemOut:
    item = await FAQItemRepository(session).create(
        tenant,
        question_text=body.question_text,
        answer_text=body.answer_text,
        keywords=body.keywords,
    )
    await session.commit()
    return FAQItemOut.model_validate(item)


@router.patch("/items/{faq_item_id}", response_model=FAQItemOut)
async def update_item(
    faq_item_id: uuid.UUID, body: FAQItemUpdate, tenant: CurrentTenant, session: DbSession
) -> FAQItemOut:
    item = await FAQItemRepository(session).update(
        tenant, faq_item_id, **body.model_dump(exclude_unset=True)
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "FAQ item not found")
    await session.commit()
    return FAQItemOut.model_validate(item)
