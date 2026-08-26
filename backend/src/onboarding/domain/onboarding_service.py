from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import ItemRepository
from identity.adapters.repository import MerchantRepository
from identity.domain.models import Merchant
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from onboarding.domain.state_machine import transition_onboarding_status
from shared.tenant import TenantContext


class MerchantNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class OnboardingChecklist:
    onboarding_status: str
    whatsapp_connected: bool
    profile_completed: bool
    has_available_menu_item: bool


async def _require_merchant(session: AsyncSession, tenant: TenantContext) -> Merchant:
    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    if merchant is None:
        raise MerchantNotFoundError(str(tenant.merchant_id))
    return merchant


async def advance_after_whatsapp_connected(
    session: AsyncSession, tenant: TenantContext
) -> Merchant:
    """Connecting WhatsApp (pasting phone_number_id + access_token, per the
    Phase 5 deviation note -- no live Meta OAuth handshake) stands in for
    both the `meta_connected` and `whatsapp_verified` steps at once, since
    there's no independent action to trigger one without the other blind.
    A no-op if the merchant is already past this point (e.g. updating
    credentials later doesn't move onboarding_status backwards or re-fire)."""
    merchant = await _require_merchant(session, tenant)
    if merchant.onboarding_status == "registered":
        transition_onboarding_status(merchant, "meta_connected")
    if merchant.onboarding_status == "meta_connected":
        transition_onboarding_status(merchant, "whatsapp_verified")
    await session.flush()
    return merchant


async def advance_after_profile_completed(session: AsyncSession, tenant: TenantContext) -> Merchant:
    merchant = await _require_merchant(session, tenant)
    if merchant.onboarding_status == "whatsapp_verified":
        transition_onboarding_status(merchant, "profile_completed")
    await session.flush()
    return merchant


async def try_advance_for_catalog_ready(session: AsyncSession, tenant: TenantContext) -> Merchant:
    """`catalog_ready` is gated by Catalog Service data (>=1 available
    Item) but owned by Onboarding Service (ARCHITECTURE.md Section 5:
    "Onboarding Service checks the gate") -- called from the catalog
    endpoints after anything that could newly satisfy the gate, and from the
    status endpoint as a fallback. `live` has no further precondition once
    `catalog_ready` is reached, so both steps cascade in one call."""
    merchant = await _require_merchant(session, tenant)
    if merchant.onboarding_status == "profile_completed":
        available_items = await ItemRepository(session).list(tenant, include_unavailable=False)
        if available_items:
            transition_onboarding_status(merchant, "catalog_ready")
    if merchant.onboarding_status == "catalog_ready":
        transition_onboarding_status(merchant, "live")
    await session.flush()
    return merchant


async def get_checklist(session: AsyncSession, tenant: TenantContext) -> OnboardingChecklist:
    merchant = await try_advance_for_catalog_ready(session, tenant)
    waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
    available_items = await ItemRepository(session).list(tenant, include_unavailable=False)

    return OnboardingChecklist(
        onboarding_status=merchant.onboarding_status,
        whatsapp_connected=waba is not None and waba.connection_status == "connected",
        profile_completed=merchant.kitchen_address_line1 is not None,
        has_available_menu_item=len(available_items) > 0,
    )
