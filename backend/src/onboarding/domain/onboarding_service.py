from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from appointments.adapters.scheduling_repository import AppointmentServiceRepository
from catalog.adapters.repository import ItemRepository
from identity.adapters.repository import MerchantRepository
from identity.domain.models import Merchant, MerchantVertical
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from onboarding.domain.state_machine import transition_onboarding_status
from shared.tenant import TenantContext


class MerchantNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class OnboardingChecklist:
    onboarding_status: str
    vertical: str | None
    whatsapp_connected: bool
    profile_completed: bool
    has_available_item: bool
    has_available_service: bool


async def _require_merchant(session: AsyncSession, tenant: TenantContext) -> Merchant:
    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    if merchant is None:
        raise MerchantNotFoundError(str(tenant.merchant_id))
    return merchant


async def advance_after_vertical_selected(session: AsyncSession, tenant: TenantContext) -> Merchant:
    """A no-op if the merchant is already past `registered` -- same
    idempotency convention as advance_after_whatsapp_connected/
    advance_after_profile_completed below, so a retried request never
    raises IllegalOnboardingTransitionError."""
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
    """`catalog_ready` is gated by Catalog Service data (>=1 available
    Item) but owned by Onboarding Service (ARCHITECTURE.md Section 5:
    "Onboarding Service checks the gate") -- called from the catalog
    endpoints after anything that could newly satisfy the gate, and from the
    status endpoint as a fallback. `live` has no further precondition once
    `catalog_ready` is reached, so both steps cascade in one call.

    MULTI_VERTICAL_PLAN.md's Decision 5: the *gate condition* (>=1 available
    row) only applies to the restaurant vertical. AppointmentService rows
    are optional by design (a merchant with zero rows just has one generic
    appointment type -- see that model's docstring), so requiring one
    before going live would add friction the appointment vertical doesn't
    need -- an appointment merchant cascades through `catalog_ready` and
    straight on to `live` unconditionally instead, the same non-blocking
    pattern the (also-optional) FAQ step already uses. Still routed through
    `catalog_ready` as an intermediate status (rather than a direct
    profile_completed -> live edge) so ONBOARDING_TRANSITIONS keeps its
    "strictly linear, no step-skipping" invariant -- every merchant, either
    vertical, passes through every status in ONBOARDING_STATUSES in order;
    only whether the *gate* blocks progress differs."""
    merchant = await _require_merchant(session, tenant)
    is_appointment = merchant.vertical == MerchantVertical.APPOINTMENT.value

    if merchant.onboarding_status == "profile_completed":
        gate_satisfied = is_appointment or bool(
            await ItemRepository(session).list(tenant, include_unavailable=False)
        )
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
        vertical=merchant.vertical,
        whatsapp_connected=waba is not None and waba.connection_status == "connected",
        profile_completed=merchant.business_address_line1 is not None,
        has_available_item=len(available_items) > 0,
        has_available_service=len(active_services) > 0,
    )
