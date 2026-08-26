import uuid

from fastapi import APIRouter, HTTPException, status

from catalog.adapters.repository import ItemRepository
from customers.adapters.repository import AddressRepository, CustomerRepository
from identity.adapters.repository import MerchantRepository
from identity.domain.models import Merchant
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from ordering_flow.api.schemas import (
    OrderingFlowAddressOut,
    OrderingFlowCheckoutRequest,
    OrderingFlowCheckoutResponse,
    OrderingFlowCustomerLookupOut,
    PublicItemOut,
    PublicMenuOut,
)
from ordering_flow.domain.checkout import (
    CheckoutItem,
    ItemNotFoundError,
    NewDeliveryAddress,
    perform_checkout,
)
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
    items = await ItemRepository(session).list(tenant, include_unavailable=False)
    waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
    return PublicMenuOut(
        business_name=merchant.business_name,
        items=[PublicItemOut.model_validate(item) for item in items],
        merchant_whatsapp_number=waba.display_phone_number if waba else None,
    )


@router.get("/{merchant_id}/customer-lookup", response_model=OrderingFlowCustomerLookupOut)
async def customer_lookup(
    merchant_id: uuid.UUID, whatsapp_number: str, session: DbSession
) -> OrderingFlowCustomerLookupOut:
    """Public and unauthenticated, matching the rest of this module's
    security model (checkout already creates customers by phone number
    with no auth) -- lets the webview prefill a returning customer's name
    and saved address once they finish entering their WhatsApp number,
    instead of asking every time. Strictly scoped to this merchant_id, so
    one merchant's customers never surface through another merchant's
    ordering page. 404s for a customer that doesn't exist yet -- that's
    the normal new-customer case, not an error."""
    merchant = await _get_merchant_or_404(session, merchant_id)
    tenant = TenantContext(merchant_id=merchant.merchant_id)

    customer = await CustomerRepository(session).get_by_whatsapp_number(tenant, whatsapp_number)
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")

    address = await AddressRepository(session).get_primary_for_customer(
        tenant, customer.customer_id
    )
    return OrderingFlowCustomerLookupOut(
        display_name=customer.display_name,
        address=OrderingFlowAddressOut.model_validate(address) if address else None,
        default_contact_phone=customer.default_contact_phone,
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

    new_delivery_address = (
        NewDeliveryAddress(
            line1=body.delivery_address.line1,
            city=body.delivery_address.city,
            pincode=body.delivery_address.pincode,
            line2=body.delivery_address.line2,
            landmark=body.delivery_address.landmark,
        )
        if body.delivery_address is not None
        else None
    )

    try:
        result = await perform_checkout(
            session,
            tenant,
            customer_whatsapp_number=body.customer_whatsapp_number,
            customer_display_name=body.customer_display_name,
            items=[
                CheckoutItem(item_id=line.item_id, quantity=line.quantity)
                for line in body.items
            ],
            payment_method=body.payment_method,
            order_type=body.order_type,
            new_delivery_address=new_delivery_address,
            contact_phone=body.contact_phone,
        )
    except ItemNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    return OrderingFlowCheckoutResponse(
        order_id=result.order.order_id,
        order_number=result.order.order_number,
        payment_status=result.order.payment_status,
        fulfillment_status=result.order.fulfillment_status,
        total=str(result.order.total),
        payment_link_url=result.payment_link_url,
    )
