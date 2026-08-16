import logging
import uuid
from typing import Any

from fastapi import APIRouter, Response, status

from catalog.adapters.repository import MenuItemRepository
from flows.api.schemas import FlowDataExchangeRequest
from flows.domain.encryption import FlowDecryptionError, decrypt_request, encrypt_response
from flows.domain.menu_order import NoItemsSelectedError, build_menu_screen_data, resolve_cart
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
    server data (menu list, computed cart total) round-trips through here --
    the endpoint_uri configured on the merchant's Flow (see
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

    response_data = await _handle_action(session, tenant, payload)
    encrypted = encrypt_response(response=response_data, aes_key=aes_key, iv=iv)
    return Response(content=encrypted, media_type="text/plain", status_code=status.HTTP_200_OK)


async def _handle_action(
    session: DbSession, tenant: TenantContext, payload: dict[str, Any]
) -> dict[str, Any]:
    action = payload.get("action")

    if action == "ping":
        return {"data": {"status": "active"}}

    if action == "INIT" or action == "BACK":
        return await _menu_screen_response(session, tenant)

    if action == "data_exchange" and payload.get("screen") == "MENU":
        selected = list((payload.get("data") or {}).get("selected_items") or [])
        menu_items = await MenuItemRepository(session).list(tenant, include_unavailable=False)
        try:
            cart = resolve_cart(selected_item_ids=selected, menu_items=menu_items)
        except NoItemsSelectedError:
            return await _menu_screen_response(session, tenant)
        return {"screen": "DETAILS", "data": {"cart_summary": cart.summary_text}}

    # Anything else (an action/screen combo the Flow JSON doesn't actually
    # produce) -- fail safe back to the menu rather than erroring the whole
    # exchange, since a stuck Flow with no recovery is worse for the
    # customer than restarting at MENU.
    return await _menu_screen_response(session, tenant)


async def _menu_screen_response(session: DbSession, tenant: TenantContext) -> dict[str, Any]:
    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    menu_items = await MenuItemRepository(session).list(tenant, include_unavailable=False)
    business_name = merchant.business_name if merchant else "Order"
    return {
        "screen": "MENU",
        "data": build_menu_screen_data(business_name=business_name, menu_items=menu_items),
    }
