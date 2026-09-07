import datetime

from fastapi import APIRouter, HTTPException, status

from billing.adapters.repository import PlanRepository, SubscriptionRepository
from billing.domain.gating import effective_tier
from catalog.adapters.repository import ItemRepository
from customers.domain.identity_resolution import resolve_customer_by_whatsapp_id
from identity.adapters.repository import MerchantRepository
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from ordering_flow.api.schemas import (
    OrderingFlowAddressOut,
    OrderingFlowCheckoutRequest,
    OrderingFlowCheckoutResponse,
    OrderingFlowCustomerLookupOut,
    PublicCatalogOut,
    PublicItemOut,
)
from ordering_flow.domain.checkout import (
    CheckoutItem,
    ItemNotFoundError,
    ItemUnavailableError,
    NewDeliveryAddress,
    perform_checkout,
)
from shared.deps import DbSession, PublicTenant
from shared.tenant import TenantContext

router = APIRouter(prefix="/api/v1/ordering-flow", tags=["ordering_flow"])


@router.get("/{merchant_id}/catalog", response_model=PublicCatalogOut)
async def get_public_catalog(tenant: PublicTenant, session: DbSession) -> PublicCatalogOut:
    """Public and unauthenticated -- this is what the customer-facing
    ordering webview (the OrderingSurface fallback, per ARCHITECTURE.md
    Section 6, in place of a live WhatsApp Flow connection) loads."""
    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    if merchant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant not found")
    items = await ItemRepository(session).list(tenant, include_unavailable=False)
    waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
    return PublicCatalogOut(
        business_name=merchant.business_name,
        items=[PublicItemOut.model_validate(item) for item in items],
        merchant_whatsapp_number=waba.display_phone_number if waba else None,
        hide_branding=await _hide_branding(session, tenant),
    )


async def _hide_branding(session: DbSession, tenant: TenantContext) -> bool:
    """Starter shows the "Powered by Orderflow" footer; Growth/Pro hide it.
    Fails open to False (show branding) whenever there's no Subscription
    row or its Plan can't be resolved -- never crash the public menu page
    over a billing lookup issue."""
    subscription = await SubscriptionRepository(session).get(tenant)
    if subscription is None:
        return False
    plan = await PlanRepository(session).get(subscription.plan_id)
    if plan is None:
        return False
    tier = effective_tier(subscription, plan, datetime.datetime.now(datetime.UTC))
    return tier != "starter"


@router.get("/{merchant_id}/customer-lookup", response_model=OrderingFlowCustomerLookupOut)
async def customer_lookup(
    tenant: PublicTenant, whatsapp_number: str, session: DbSession
) -> OrderingFlowCustomerLookupOut:
    """Public and unauthenticated, matching the rest of this module's
    security model (checkout already creates customers by phone number
    with no auth) -- lets the webview prefill a returning customer's name
    and saved address once they finish entering their WhatsApp number,
    instead of asking every time. Strictly scoped to this merchant_id, so
    one merchant's customers never surface through another merchant's
    ordering page. 404s for a customer that doesn't exist yet -- that's
    the normal new-customer case, not an error."""
    resolved = await resolve_customer_by_whatsapp_id(
        session, tenant, whatsapp_number, include_address=True
    )
    if resolved is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")

    return OrderingFlowCustomerLookupOut(
        display_name=resolved.customer.display_name,
        address=OrderingFlowAddressOut.model_validate(resolved.address)
        if resolved.address
        else None,
        default_contact_phone=resolved.customer.default_contact_phone,
        last_payment_method=resolved.customer.last_payment_method,
    )


@router.post(
    "/{merchant_id}/checkout",
    response_model=OrderingFlowCheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def checkout(
    tenant: PublicTenant, body: OrderingFlowCheckoutRequest, session: DbSession
) -> OrderingFlowCheckoutResponse:
    """The real customer-facing checkout -- same
    ordering_flow.domain.checkout.perform_checkout the dashboard's
    test-checkout (Phase 5) uses, so both paths stay in sync by
    construction rather than by discipline."""
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
    except ItemUnavailableError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    return OrderingFlowCheckoutResponse(
        order_id=result.order.order_id,
        order_number=result.order.order_number,
        payment_status=result.order.payment_status,
        fulfillment_status=result.order.fulfillment_status,
        total=str(result.order.total),
        payment_link_url=result.payment_link_url,
    )
