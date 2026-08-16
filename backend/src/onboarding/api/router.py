from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from conversation.adapters.whatsapp_client import WhatsAppSender, get_whatsapp_sender
from flows.domain.setup import FlowSetupError, setup_whatsapp_flow, update_flow_assets
from identity.adapters.repository import MerchantRepository
from identity.domain.models import Merchant
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from onboarding.api.schemas import (
    KitchenProfileOut,
    KitchenProfileUpdate,
    OnboardingStatusOut,
    WhatsAppFlowSetupRequest,
    WhatsAppFlowSetupResult,
    WhatsAppSettingsOut,
    WhatsAppSettingsUpdate,
    WhatsAppTestMessageRequest,
    WhatsAppTestMessageResult,
)
from onboarding.domain.models import WhatsAppBusinessAccount
from onboarding.domain.onboarding_service import (
    advance_after_profile_completed,
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
        )
    return WhatsAppSettingsOut(
        phone_number_id=account.phone_number_id,
        display_phone_number=account.display_phone_number,
        access_token_set=account.access_token_encrypted is not None,
        connection_status=account.connection_status,
    )


def _profile_to_out(merchant: Merchant) -> KitchenProfileOut:
    return KitchenProfileOut(
        address_line1=merchant.kitchen_address_line1,
        address_line2=merchant.kitchen_address_line2,
        city=merchant.kitchen_city,
        pincode=merchant.kitchen_pincode,
        cuisine_type=merchant.cuisine_type,
        fssai_license_no=merchant.fssai_license_no,
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


@router.post("/whatsapp/flow-sync", status_code=status.HTTP_204_NO_CONTENT)
async def sync_whatsapp_flow_endpoint(tenant: CurrentTenant, session: DbSession) -> None:
    """Pushes the current order_flow.json to Meta for a merchant who
    already ran /whatsapp/flow-setup once -- for whenever the Flow JSON
    itself changes (new screens/fields) and an already-onboarded
    merchant's live Flow needs to pick up the update, without recreating
    the whole Flow (new flow_id, new RSA key pair, re-publish) from
    scratch. See flows/domain/setup.py's update_flow_assets."""
    account = await WhatsAppBusinessAccountRepository(session).get(tenant)
    if account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "WhatsApp credentials not configured")

    try:
        await update_flow_assets(session, tenant, account)
    except FlowSetupError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Flow sync failed at '{exc.step}': {exc.detail}"
        ) from exc


@router.get("/profile", response_model=KitchenProfileOut)
async def get_kitchen_profile(tenant: CurrentTenant, session: DbSession) -> KitchenProfileOut:
    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    if merchant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant not found")
    return _profile_to_out(merchant)


@router.put("/profile", response_model=KitchenProfileOut)
async def update_kitchen_profile(
    body: KitchenProfileUpdate, tenant: CurrentTenant, session: DbSession
) -> KitchenProfileOut:
    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    if merchant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant not found")

    merchant.kitchen_address_line1 = body.address_line1
    merchant.kitchen_address_line2 = body.address_line2
    merchant.kitchen_city = body.city
    merchant.kitchen_pincode = body.pincode
    merchant.cuisine_type = body.cuisine_type
    merchant.fssai_license_no = body.fssai_license_no

    await advance_after_profile_completed(session, tenant)
    await session.commit()
    return _profile_to_out(merchant)


@router.get("/status", response_model=OnboardingStatusOut)
async def get_onboarding_status(tenant: CurrentTenant, session: DbSession) -> OnboardingStatusOut:
    checklist = await get_checklist(session, tenant)
    await session.commit()
    return OnboardingStatusOut(
        onboarding_status=checklist.onboarding_status,
        whatsapp_connected=checklist.whatsapp_connected,
        profile_completed=checklist.profile_completed,
        has_available_menu_item=checklist.has_available_menu_item,
    )
