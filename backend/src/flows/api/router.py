import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Response, status

from catalog.adapters.repository import ItemRepository
from catalog.domain.models import Item
from customers.domain.identity_resolution import resolve_customer_by_whatsapp_id
from flows.api.schemas import FlowDataExchangeRequest
from flows.domain.appointment_booking import build_booking_screen_data
from flows.domain.encryption import FlowDecryptionError, decrypt_request, encrypt_response
from flows.domain.images import fetch_and_compress_image
from flows.domain.order_builder import (
    NoItemsSelectedError,
    build_category_screen_data,
    build_details_screen_data,
    build_items_screen_data,
    resolve_cart,
)
from identity.adapters.repository import MerchantRepository
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from shared.deps import DbSession
from shared.encryption import decrypt
from shared.tenant import TenantContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/whatsapp/flows", tags=["flows"])


@router.post("/{merchant_id}/data-exchange")
async def data_exchange(
    merchant_id: uuid.UUID, body: FlowDataExchangeRequest, session: DbSession
) -> Response:
    """Every screen transition in flows/assets/order_flow.json that needs
    server data (categories, per-category item list, computed cart total,
    a returning customer's saved address) round-trips through here -- the
    endpoint_uri configured on the merchant's Flow (see
    scripts/setup_whatsapp_flow.py) points at this exact route, with
    merchant_id in the path so we know *whose* RSA private key to try
    before we've decrypted anything (the encrypted body carries no plaintext
    tenant identifier). Unauthenticated by JWT -- correct decryption under
    that merchant's key is what proves the request is really from WhatsApp
    for this merchant, not a Bearer token."""
    tenant = TenantContext(merchant_id=merchant_id)
    waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
    if waba is None or waba.flow_private_key_encrypted is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    try:
        private_key_pem = decrypt(waba.flow_private_key_encrypted)
        payload, aes_key, iv = decrypt_request(
            encrypted_flow_data_b64=body.encrypted_flow_data,
            encrypted_aes_key_b64=body.encrypted_aes_key,
            initial_vector_b64=body.initial_vector,
            private_key_pem=private_key_pem,
        )
    except FlowDecryptionError:
        logger.warning("Flow data-exchange decryption failed for merchant %s", merchant_id)
        # 421 tells WhatsApp our public key may have rotated -- it re-fetches
        # and retries, rather than surfacing a broken Flow to the customer.
        return Response(status_code=status.HTTP_421_MISDIRECTED_REQUEST)

    logger.info(
        "Flow data-exchange request for merchant %s: action=%r screen=%r data_keys=%r",
        merchant_id,
        payload.get("action"),
        payload.get("screen"),
        list((payload.get("data") or {}).keys()),
    )
    response_data = await _handle_action(session, tenant, payload)
    logger.info(
        "Flow data-exchange response for merchant %s: screen=%r",
        merchant_id,
        response_data.get("screen"),
    )
    encrypted = encrypt_response(response=response_data, aes_key=aes_key, iv=iv)
    return Response(content=encrypted, media_type="text/plain", status_code=status.HTTP_200_OK)


@router.post("/{merchant_id}/appointment-data-exchange")
async def appointment_data_exchange(
    merchant_id: uuid.UUID, body: FlowDataExchangeRequest, session: DbSession
) -> Response:
    """Same decrypt -> dispatch -> encrypt shape as data_exchange() above,
    for the separate, single-screen appointment-booking Flow (see
    flows/assets/appointment_flow.json). A distinct route (rather than
    branching data_exchange() itself on some payload field) because the
    two Flows' endpoint_uris are configured independently against Meta
    (see scripts/setup_whatsapp_appointment_flow.py) and have no
    navigation state in common to share -- keeping them as two small,
    independently-readable functions beats one route with a "which flow
    is this" branch threaded through it. They do share the same
    business-level RSA key pair (waba.flow_private_key_encrypted), so the
    404/421 handling below is identical."""
    tenant = TenantContext(merchant_id=merchant_id)
    waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
    if waba is None or waba.flow_private_key_encrypted is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    try:
        private_key_pem = decrypt(waba.flow_private_key_encrypted)
        payload, aes_key, iv = decrypt_request(
            encrypted_flow_data_b64=body.encrypted_flow_data,
            encrypted_aes_key_b64=body.encrypted_aes_key,
            initial_vector_b64=body.initial_vector,
            private_key_pem=private_key_pem,
        )
    except FlowDecryptionError:
        logger.warning(
            "Appointment flow data-exchange decryption failed for merchant %s", merchant_id
        )
        return Response(status_code=status.HTTP_421_MISDIRECTED_REQUEST)

    logger.info(
        "Appointment flow data-exchange request for merchant %s: action=%r screen=%r",
        merchant_id,
        payload.get("action"),
        payload.get("screen"),
    )
    response_data = await _handle_appointment_action(session, tenant, payload)
    logger.info(
        "Appointment flow data-exchange response for merchant %s: screen=%r",
        merchant_id,
        response_data.get("screen"),
    )
    encrypted = encrypt_response(response=response_data, aes_key=aes_key, iv=iv)
    return Response(content=encrypted, media_type="text/plain", status_code=status.HTTP_200_OK)


async def _handle_appointment_action(
    session: DbSession, tenant: TenantContext, payload: dict[str, Any]
) -> dict[str, Any]:
    """The appointment Flow is single-screen and terminal (see
    flows/assets/appointment_flow.json's routing_model) -- there's no
    screen-to-screen navigation to dispatch on, unlike _handle_action
    above. `ping` gets the standard health-check reply; INIT (and any
    other/unrecognized action, as a fail-safe -- same rationale as
    _handle_action's fallback) always (re)renders the one BOOKING screen
    with a fresh set of date/time options, prefilling name/email for a
    customer resolve_customer_by_whatsapp_id recognizes from flow_token --
    same shared identity-resolution entrypoint _handle_action's ITEMS
    branch uses, so a customer recognized on one Flow is recognized on the
    other (both write the same Customer row)."""
    action = payload.get("action")

    if action == "ping":
        return {"data": {"status": "active"}}

    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    business_name = merchant.business_name if merchant else "Book"
    resolved = await resolve_customer_by_whatsapp_id(session, tenant, payload.get("flow_token"))
    return {
        "screen": "BOOKING",
        "data": build_booking_screen_data(
            business_name=business_name,
            saved_customer_name=resolved.customer.display_name if resolved else None,
            saved_customer_email=resolved.customer.email if resolved else None,
        ),
    }


async def _handle_action(
    session: DbSession, tenant: TenantContext, payload: dict[str, Any]
) -> dict[str, Any]:
    action = payload.get("action")
    screen = payload.get("screen")
    data = payload.get("data") or {}

    if action == "ping":
        return {"data": {"status": "active"}}

    if action == "data_exchange" and screen == "CATEGORY":
        category = data.get("category")
        if category:
            items = await ItemRepository(session).list(tenant, include_unavailable=False)
            await _ensure_images_cached(
                session, [item for item in items if item.category == category]
            )
            return {
                "screen": "ITEMS",
                "data": build_items_screen_data(category=category, items=items),
            }
        # No category selected (shouldn't happen -- RadioButtonsGroup is
        # required client-side) -- fall through to re-showing CATEGORY.

    if action == "data_exchange" and screen == "ITEMS":
        selected = list(data.get("selected_items") or [])
        items = await ItemRepository(session).list(tenant, include_unavailable=False)
        try:
            cart = resolve_cart(selected_item_ids=selected, items=items)
        except NoItemsSelectedError:
            pass
        else:
            resolved = await resolve_customer_by_whatsapp_id(
                session, tenant, payload.get("flow_token"), include_address=True
            )
            return {
                "screen": "DETAILS",
                "data": build_details_screen_data(
                    cart_summary=cart.summary_text,
                    saved_address=resolved.address if resolved else None,
                    saved_customer_name=resolved.customer.display_name if resolved else None,
                    saved_default_contact_phone=(
                        resolved.customer.default_contact_phone if resolved else None
                    ),
                ),
            }
        # No items actually resolved (stale/empty selection) -- fall
        # through to re-showing CATEGORY rather than a dead-end ITEMS
        # screen with nothing to add to it.

    # INIT, BACK, and any action/screen combo the Flow JSON doesn't
    # actually produce -- fail safe back to category selection rather than
    # erroring the whole exchange, since a stuck Flow with no recovery is
    # worse for the customer than restarting from the top.
    return await _category_screen_response(session, tenant)


async def _category_screen_response(session: DbSession, tenant: TenantContext) -> dict[str, Any]:
    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    items = await ItemRepository(session).list(tenant, include_unavailable=False)
    business_name = merchant.business_name if merchant else "Order"
    return {
        "screen": "CATEGORY",
        "data": build_category_screen_data(business_name=business_name, items=items),
    }


async def _ensure_images_cached(session: DbSession, items: list[Item]) -> None:
    """Populates Item.flow_image_base64 for any item in this category
    that has an image_url but hasn't been fetched/compressed yet -- fetched
    concurrently so a cold cache (a brand-new category) doesn't serialize
    N network round trips on the customer's screen load. Once cached, later
    views of this category are instant; this only ever runs once per item
    unless image_url changes (nothing currently invalidates the cache on
    an image_url edit -- a known gap, not silent breakage, since a merchant
    changing a photo is rare and the old cached one just keeps showing)."""
    to_fetch = [item for item in items if item.image_url and not item.flow_image_base64]
    if not to_fetch:
        return

    results = await asyncio.gather(
        *(fetch_and_compress_image(item.image_url) for item in to_fetch if item.image_url)
    )
    changed = False
    for item, compressed in zip(to_fetch, results, strict=True):
        if compressed:
            item.flow_image_base64 = compressed
            changed = True
    if changed:
        await session.commit()
