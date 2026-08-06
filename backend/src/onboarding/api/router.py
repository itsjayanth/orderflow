from fastapi import APIRouter, HTTPException, status

from identity.adapters.repository import MerchantRepository
from identity.domain.models import Merchant
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from onboarding.api.schemas import (
    KitchenProfileOut,
    KitchenProfileUpdate,
    OnboardingStatusOut,
    WhatsAppSettingsOut,
    WhatsAppSettingsUpdate,
)
from onboarding.domain.models import WhatsAppBusinessAccount
from onboarding.domain.onboarding_service import (
    advance_after_profile_completed,
    advance_after_whatsapp_connected,
    get_checklist,
)
from shared.deps import CurrentTenant, DbSession
from shared.encryption import encrypt

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


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
