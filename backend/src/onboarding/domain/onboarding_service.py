from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from appointments.adapters.scheduling_repository import AppointmentServiceRepository
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
    restaurant_enabled: bool
    appointment_enabled: bool
    whatsapp_connected: bool
    profile_completed: bool
    has_available_item: bool
    has_available_service: bool


async def restaurant_ready(session: AsyncSession, tenant: TenantContext) -> bool:
    """The restaurant vertical's readiness gate: >=1 available Item. Shared
    between the onboarding cascade below and conversation/domain/handler.py's
    WhatsApp menu builder, so "ready enough to go live" and "ready enough to
    show in the WhatsApp menu" can never drift apart -- VERTICAL_TOGGLE_PLAN.md's
    single empty-flow guard, not two."""
    return bool(await ItemRepository(session).list(tenant, include_unavailable=False))


async def appointment_ready(session: AsyncSession, tenant: TenantContext) -> bool:
    """The appointment vertical's readiness gate: >=1 active AppointmentService.
    VERTICAL_TOGGLE_PLAN.md deliberately overrides MULTI_VERTICAL_PLAN.md's
    Decision 5 ("appointment services are optional, no required gate") --
    under the additive/toggle model an enabled-but-empty appointment vertical
    is exactly the "empty flow" a customer must never be shown, so this is
    now symmetric with restaurant_ready above."""
    return bool(await AppointmentServiceRepository(session).list(tenant, include_inactive=False))


async def _require_merchant(session: AsyncSession, tenant: TenantContext) -> Merchant:
    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    if merchant is None:
        raise MerchantNotFoundError(str(tenant.merchant_id))
    return merchant


async def advance_after_vertical_selected(session: AsyncSession, tenant: TenantContext) -> Merchant:
    """Called every time PUT /api/v1/onboarding/verticals succeeds --
    including from Settings' "Business types" section, long after the
    merchant is already `live`. A no-op whenever the merchant is already
    past `registered` (same idempotency convention as
    advance_after_whatsapp_connected/advance_after_profile_completed below),
    so adding a vertical later never re-fires or regresses onboarding_status
    -- VERTICAL_TOGGLE_PLAN.md's "no vertical is a special step to lock the
    wizard on" applies here too."""
    merchant = await _require_merchant(session, tenant)
    if merchant.onboarding_status == "registered":
        transition_onboarding_status(merchant, "vertical_selected")
    await session.flush()
    return merchant


async def advance_after_whatsapp_connected(
    session: AsyncSession, tenant: TenantContext
) -> Merchant:
    """Connecting WhatsApp (pasting phone_number_id + access_token, per the
    Phase 5 deviation note -- no live Meta OAuth handshake) stands in for
    both the `meta_connected` and `whatsapp_verified` steps at once, since
    there's no independent action to trigger one without the other blind.
    A no-op if the merchant is already past this point (e.g. updating
    credentials later doesn't move onboarding_status backwards or re-fire).

    Starts from `vertical_selected`, not `registered` -- the vertical-choice
    step (MULTI_VERTICAL_PLAN.md Phase M1) must happen first, so a merchant
    still sitting at `registered` here means the wizard was driven out of
    order and this correctly no-ops rather than skipping that step."""
    merchant = await _require_merchant(session, tenant)
    if merchant.onboarding_status == "vertical_selected":
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
    """`catalog_ready` is gated by Catalog/Appointment-Service data but owned
    by Onboarding Service (ARCHITECTURE.md Section 5: "Onboarding Service
    checks the gate") -- called from the catalog and appointment-service
    endpoints after anything that could newly satisfy the gate, and from the
    status endpoint as a fallback. `live` has no further precondition once
    `catalog_ready` is reached, so both steps cascade in one call.

    VERTICAL_TOGGLE_PLAN.md: a merchant can have *both* verticals enabled
    now, so the gate is "every enabled vertical is ready" (restaurant_ready
    / appointment_ready above), not a single vertical's check -- a vertical
    that isn't enabled trivially satisfies its own half of the gate. This
    also supersedes MULTI_VERTICAL_PLAN.md's Decision 5 (appointment was
    unconditionally ungated): under the additive model, an enabled-but-empty
    appointment vertical is exactly the "don't show an empty flow" case the
    gate exists to prevent, so it's now symmetric with restaurant. Still
    routed through `catalog_ready` as an intermediate status (rather than a
    direct profile_completed -> live edge) so ONBOARDING_TRANSITIONS keeps
    its "strictly linear, no step-skipping" invariant."""
    merchant = await _require_merchant(session, tenant)

    if merchant.onboarding_status == "profile_completed":
        gate_satisfied = (
            not merchant.restaurant_enabled or await restaurant_ready(session, tenant)
        ) and (not merchant.appointment_enabled or await appointment_ready(session, tenant))
        if gate_satisfied:
            transition_onboarding_status(merchant, "catalog_ready")
    if merchant.onboarding_status == "catalog_ready":
        transition_onboarding_status(merchant, "live")
    await session.flush()
    return merchant


async def get_checklist(session: AsyncSession, tenant: TenantContext) -> OnboardingChecklist:
    merchant = await try_advance_for_catalog_ready(session, tenant)
    waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
    available_items = await ItemRepository(session).list(tenant, include_unavailable=False)
    active_services = await AppointmentServiceRepository(session).list(
        tenant, include_inactive=False
    )

    return OnboardingChecklist(
        onboarding_status=merchant.onboarding_status,
        restaurant_enabled=merchant.restaurant_enabled,
        appointment_enabled=merchant.appointment_enabled,
        whatsapp_connected=waba is not None and waba.connection_status == "connected",
        profile_completed=merchant.business_address_line1 is not None,
        has_available_item=len(available_items) > 0,
        has_available_service=len(active_services) > 0,
    )
