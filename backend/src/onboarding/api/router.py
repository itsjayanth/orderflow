from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from conversation.adapters.whatsapp_client import WhatsAppSender, get_whatsapp_sender
from flows.domain.setup import (
    FlowSetupError,
    get_flow_validation,
    setup_whatsapp_appointment_flow,
    setup_whatsapp_flow,
    update_appointment_flow_assets,
    update_flow_assets,
)
from identity.adapters.repository import MerchantRepository
from identity.domain.models import Merchant, NoVerticalSelectedError
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from onboarding.api.schemas import (
    BusinessProfileOut,
    BusinessProfileUpdate,
    EmbeddedSignupRequest,
    EmbeddedSignupResult,
    MessagingTierOut,
    MessagingTierUpdate,
    OnboardingStatusOut,
    VerticalsSelectionOut,
    VerticalsSelectionRequest,
    WhatsAppFlowSetupRequest,
    WhatsAppFlowSetupResult,
    WhatsAppSettingsOut,
    WhatsAppSettingsUpdate,
    WhatsAppTestMessageRequest,
    WhatsAppTestMessageResult,
)
from onboarding.domain.embedded_signup import (
    STATUS_CONNECTED,
    EmbeddedSignupError,
    complete_embedded_signup,
)
from onboarding.domain.models import WhatsAppBusinessAccount
from onboarding.domain.onboarding_service import (
    advance_after_profile_completed,
    advance_after_vertical_selected,
    advance_after_whatsapp_connected,
    get_checklist,
)
from shared.deps import CurrentTenant, DbSession
from shared.encryption import decrypt, encrypt

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])

WhatsAppSenderDep = Annotated[WhatsAppSender, Depends(get_whatsapp_sender)]


def _whatsapp_to_out(account: WhatsAppBusinessAccount | None) -> WhatsAppSettingsOut:
    if account is None:
        return WhatsAppSettingsOut(
            phone_number_id=None,
            display_phone_number=None,
            access_token_set=False,
            connection_status="pending",
            messaging_tier_daily_limit=250,
        )
    return WhatsAppSettingsOut(
        phone_number_id=account.phone_number_id,
        display_phone_number=account.display_phone_number,
        access_token_set=account.access_token_encrypted is not None,
        connection_status=account.connection_status,
        messaging_tier_daily_limit=account.messaging_tier_daily_limit,
    )


def _profile_to_out(merchant: Merchant) -> BusinessProfileOut:
    return BusinessProfileOut(
        address_line1=merchant.business_address_line1,
        address_line2=merchant.business_address_line2,
        city=merchant.business_city,
        pincode=merchant.business_pincode,
        business_category=merchant.business_category,
        license_no=merchant.license_no,
    )


@router.put("/verticals", response_model=VerticalsSelectionOut)
async def select_verticals(
    body: VerticalsSelectionRequest, tenant: CurrentTenant, session: DbSession
) -> VerticalsSelectionOut:
    """Multi-select, and callable any number of times -- both the
    onboarding wizard's first step and, later, Settings' "Business types"
    section (to add a second vertical after going live) hit this same
    endpoint (VERTICAL_TOGGLE_PLAN.md). No one-time/immutability guard
    (that was Phase 10's rule for the old single `vertical` enum, now
    retired); the only validation is the shared invariant -- at least one
    of the two must be True."""
    try:
        merchant = await MerchantRepository(session).set_vertical_flags(
            tenant.merchant_id,
            restaurant_enabled=body.restaurant_enabled,
            appointment_enabled=body.appointment_enabled,
        )
    except NoVerticalSelectedError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Select at least one business type",
        ) from exc

    await advance_after_vertical_selected(session, tenant)
    await session.commit()
    return VerticalsSelectionOut(
        restaurant_enabled=merchant.restaurant_enabled,
        appointment_enabled=merchant.appointment_enabled,
    )


@router.get("/whatsapp", response_model=WhatsAppSettingsOut)
async def get_whatsapp_settings(tenant: CurrentTenant, session: DbSession) -> WhatsAppSettingsOut:
    account = await WhatsAppBusinessAccountRepository(session).get(tenant)
    return _whatsapp_to_out(account)


@router.put("/whatsapp", response_model=WhatsAppSettingsOut)
async def update_whatsapp_settings(
    body: WhatsAppSettingsUpdate, tenant: CurrentTenant, session: DbSession
) -> WhatsAppSettingsOut:
    account = await WhatsAppBusinessAccountRepository(session).upsert(
        tenant,
        phone_number_id=body.phone_number_id,
        access_token_encrypted=encrypt(body.access_token),
        display_phone_number=body.display_phone_number,
    )
    await advance_after_whatsapp_connected(session, tenant)
    await session.commit()
    return _whatsapp_to_out(account)


@router.put("/whatsapp/messaging-tier", response_model=MessagingTierOut)
async def update_messaging_tier(
    body: MessagingTierUpdate, tenant: CurrentTenant, session: DbSession
) -> MessagingTierOut:
    account = await WhatsAppBusinessAccountRepository(session).update_messaging_tier_daily_limit(
        tenant, messaging_tier_daily_limit=body.messaging_tier_daily_limit
    )
    if account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "WhatsApp credentials not configured")
    await session.commit()
    return MessagingTierOut(messaging_tier_daily_limit=account.messaging_tier_daily_limit)


@router.post("/whatsapp/embedded-signup", response_model=EmbeddedSignupResult)
async def embedded_signup_endpoint(
    body: EmbeddedSignupRequest, tenant: CurrentTenant, session: DbSession
) -> EmbeddedSignupResult:
    """Replaces manually pasting phone_number_id + access_token: the
    frontend's "Connect your WhatsApp Business account" button runs Meta's
    Embedded Signup popup and posts whatever it returns here. See
    onboarding/domain/embedded_signup.py for the full exchange -> verify ->
    persist -> (best-effort) webhook-subscribe/register-number sequence.
    A CANCELled popup is not an error -- comes back as
    status="not_completed" with a 200, same as onboarding/domain/
    embedded_signup.py's contract."""
    try:
        result = await complete_embedded_signup(
            session,
            tenant,
            code=body.code,
            waba_id=body.waba_id,
            phone_number_id=body.phone_number_id,
            business_id=body.business_id,
            event=body.event,
            backend_base_url=body.backend_base_url,
        )
    except EmbeddedSignupError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"{exc.step}: {exc.detail}") from exc

    if result.status == STATUS_CONNECTED:
        await advance_after_whatsapp_connected(session, tenant)
    await session.commit()
    return EmbeddedSignupResult(
        status=result.status,
        message=result.message,
        phone_number_id=result.phone_number_id,
        display_phone_number=result.display_phone_number,
        connection_status=result.connection_status,
        pending_steps=result.pending_steps,
    )


@router.post("/whatsapp/test-message", response_model=WhatsAppTestMessageResult)
async def send_whatsapp_test_message(
    body: WhatsAppTestMessageRequest,
    tenant: CurrentTenant,
    session: DbSession,
    sender: WhatsAppSenderDep,
) -> WhatsAppTestMessageResult:
    account = await WhatsAppBusinessAccountRepository(session).get(tenant)
    if account is None or not account.phone_number_id or not account.access_token_encrypted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "WhatsApp credentials not configured")

    success, message = await sender.send_test_message(
        phone_number_id=account.phone_number_id,
        access_token=decrypt(account.access_token_encrypted),
        to=body.to,
    )
    return WhatsAppTestMessageResult(status="success" if success else "failed", message=message)


@router.post("/whatsapp/flow-setup", response_model=WhatsAppFlowSetupResult)
async def setup_whatsapp_flow_endpoint(
    body: WhatsAppFlowSetupRequest, tenant: CurrentTenant, session: DbSession
) -> WhatsAppFlowSetupResult:
    """One-time per-merchant setup for native WhatsApp ordering (see
    flows/domain/setup.py) -- generates the RSA key pair, uploads the
    public key to Meta, creates+publishes the Flow, and stores the
    credentials, all from inside this deployment where real Meta
    credentials already exist in the environment. Same underlying logic as
    scripts/setup_whatsapp_flow.py; this is the version to use against a
    deployed environment, since nothing needs to leave it."""
    account = await WhatsAppBusinessAccountRepository(session).get(tenant)
    if account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "WhatsApp credentials not configured")

    try:
        flow_id = await setup_whatsapp_flow(
            session,
            tenant,
            account,
            meta_waba_id=body.meta_waba_id,
            backend_base_url=body.backend_base_url,
        )
    except FlowSetupError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Flow setup failed at '{exc.step}': {exc.detail}"
        ) from exc

    await session.commit()
    return WhatsAppFlowSetupResult(flow_id=flow_id)


@router.post("/whatsapp/flow-sync")
async def sync_whatsapp_flow_endpoint(
    tenant: CurrentTenant, session: DbSession
) -> dict[str, object]:
    """Pushes the current order_flow.json to Meta for a merchant who
    already ran /whatsapp/flow-setup once -- for whenever the Flow JSON
    itself changes (new screens/fields) and an already-onboarded
    merchant's live Flow needs to pick up the update, without recreating
    the whole Flow (new flow_id, new RSA key pair, re-publish) from
    scratch. See flows/domain/setup.py's update_flow_assets.

    Returns Meta's own read-back of the Flow's status/validation_errors/
    health_status right after the upload -- a <400 response from the
    upload itself only means Meta *accepted* the file, not that it's
    structurally valid; this surfaces the same validation info Meta's
    publish-time health check would have caught, immediately rather than
    only via a customer hitting a broken screen live."""
    account = await WhatsAppBusinessAccountRepository(session).get(tenant)
    if account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "WhatsApp credentials not configured")

    try:
        await update_flow_assets(session, tenant, account)
        validation = await get_flow_validation(account, flow_id=account.whatsapp_flow_id)
    except FlowSetupError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Flow sync failed at '{exc.step}': {exc.detail}"
        ) from exc

    return validation


@router.post("/whatsapp/appointment-flow-setup", response_model=WhatsAppFlowSetupResult)
async def setup_whatsapp_appointment_flow_endpoint(
    body: WhatsAppFlowSetupRequest, tenant: CurrentTenant, session: DbSession
) -> WhatsAppFlowSetupResult:
    """One-time per-merchant setup for native WhatsApp appointment booking
    (see flows/domain/setup.py) -- generates a fresh RSA key pair, uploads
    the public key to Meta, creates+publishes the "Book an Appointment"
    Flow, and stores the credentials, all from inside this deployment
    where real Meta credentials already exist in the environment. Same
    underlying logic as scripts/setup_whatsapp_appointment_flow.py; this
    is the version to use against a deployed environment, since nothing
    needs to leave it."""
    account = await WhatsAppBusinessAccountRepository(session).get(tenant)
    if account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "WhatsApp credentials not configured")

    try:
        flow_id = await setup_whatsapp_appointment_flow(
            session,
            tenant,
            account,
            meta_waba_id=body.meta_waba_id,
            backend_base_url=body.backend_base_url,
        )
    except FlowSetupError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Flow setup failed at '{exc.step}': {exc.detail}"
        ) from exc

    await session.commit()
    return WhatsAppFlowSetupResult(flow_id=flow_id)


@router.post("/whatsapp/appointment-flow-sync")
async def sync_whatsapp_appointment_flow_endpoint(
    tenant: CurrentTenant, session: DbSession
) -> dict[str, object]:
    """Pushes the current appointment_flow.json to Meta for a merchant who
    already ran /whatsapp/appointment-flow-setup once -- for whenever the
    Flow JSON itself changes and an already-onboarded merchant's live
    Flow needs to pick up the update, without recreating the whole Flow
    (new flow_id, new RSA key pair, re-publish) from scratch. See
    flows/domain/setup.py's update_appointment_flow_assets.

    Returns Meta's own read-back of the Flow's status/validation_errors/
    health_status right after the upload, same as /whatsapp/flow-sync
    does for the order Flow."""
    account = await WhatsAppBusinessAccountRepository(session).get(tenant)
    if account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "WhatsApp credentials not configured")

    try:
        await update_appointment_flow_assets(session, tenant, account)
        validation = await get_flow_validation(
            account, flow_id=account.whatsapp_appointment_flow_id
        )
    except FlowSetupError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Flow sync failed at '{exc.step}': {exc.detail}"
        ) from exc

    return validation


@router.get("/profile", response_model=BusinessProfileOut)
async def get_business_profile(tenant: CurrentTenant, session: DbSession) -> BusinessProfileOut:
    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    if merchant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant not found")
    return _profile_to_out(merchant)


@router.put("/profile", response_model=BusinessProfileOut)
async def update_business_profile(
    body: BusinessProfileUpdate, tenant: CurrentTenant, session: DbSession
) -> BusinessProfileOut:
    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    if merchant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant not found")

    merchant.business_address_line1 = body.address_line1
    merchant.business_address_line2 = body.address_line2
    merchant.business_city = body.city
    merchant.business_pincode = body.pincode
    merchant.business_category = body.business_category
    merchant.license_no = body.license_no

    await advance_after_profile_completed(session, tenant)
    await session.commit()
    return _profile_to_out(merchant)


@router.get("/status", response_model=OnboardingStatusOut)
async def get_onboarding_status(tenant: CurrentTenant, session: DbSession) -> OnboardingStatusOut:
    checklist = await get_checklist(session, tenant)
    await session.commit()
    return OnboardingStatusOut(
        onboarding_status=checklist.onboarding_status,
        restaurant_enabled=checklist.restaurant_enabled,
        appointment_enabled=checklist.appointment_enabled,
        whatsapp_connected=checklist.whatsapp_connected,
        profile_completed=checklist.profile_completed,
        has_available_item=checklist.has_available_item,
        has_available_service=checklist.has_available_service,
    )
