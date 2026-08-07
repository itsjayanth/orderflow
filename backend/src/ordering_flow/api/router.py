import uuid

from fastapi import APIRouter, HTTPException, status

from catalog.adapters.repository import MenuItemRepository
from identity.adapters.repository import MerchantRepository
from identity.domain.models import Merchant
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from ordering_flow.api.schemas import (
    OrderingFlowCheckoutRequest,
    OrderingFlowCheckoutResponse,
    PublicMenuItemOut,
    PublicMenuOut,
)
from ordering_flow.domain.checkout import CheckoutItem, MenuItemNotFoundError, perform_checkout
from shared.deps import DbSession
from shared.tenant import TenantContext

router = APIRouter(prefix="/api/v1/ordering-flow", tags=["ordering_flow"])


async def _get_merchant_or_404(session: DbSession, merchant_id: uuid.UUID) -> Merchant:
    merchant = await MerchantRepository(session).get(merchant_id)
    if merchant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurant not found")
    return merchant


@router.get("/{merchant_id}/menu", response_model=PublicMenuOut)
async def get_public_menu(merchant_id: uuid.UUID, session: DbSession) -> PublicMenuOut:
    """Public and unauthenticated -- this is what the customer-facing
    ordering webview (the OrderingSurface fallback, per ARCHITECTURE.md
    Section 6, in place of a live WhatsApp Flow connection) loads."""
    merchant = await _get_merchant_or_404(session, merchant_id)
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    items = await MenuItemRepository(session).list(tenant, include_unavailable=False)
    waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
    return PublicMenuOut(
        business_name=merchant.business_name,
        items=[PublicMenuItemOut.model_validate(item) for item in items],
        merchant_whatsapp_number=waba.display_phone_number if waba else None,
    )


@router.post(
    "/{merchant_id}/checkout",
    response_model=OrderingFlowCheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def checkout(
    merchant_id: uuid.UUID, body: OrderingFlowCheckoutRequest, session: DbSession
) -> OrderingFlowCheckoutResponse:
    """The real customer-facing checkout -- same
    ordering_flow.domain.checkout.perform_checkout the dashboard's
    test-checkout (Phase 5) uses, so both paths stay in sync by
    construction rather than by discipline."""
    merchant = await _get_merchant_or_404(session, merchant_id)
    tenant = TenantContext(merchant_id=merchant.merchant_id)

    try:
        result = await perform_checkout(
            session,
            tenant,
            customer_whatsapp_number=body.customer_whatsapp_number,
            customer_display_name=body.customer_display_name,
            items=[
                CheckoutItem(menu_item_id=line.menu_item_id, quantity=line.quantity)
                for line in body.items
            ],
            payment_method=body.payment_method,
            order_type=body.order_type,
        )
    except MenuItemNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    return OrderingFlowCheckoutResponse(
        order_id=result.order.order_id,
        payment_status=result.order.payment_status,
        fulfillment_status=result.order.fulfillment_status,
        total=str(result.order.total),
        payment_link_url=result.payment_link_url,
    )
