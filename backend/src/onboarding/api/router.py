from fastapi import APIRouter

from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from onboarding.api.schemas import WhatsAppSettingsOut, WhatsAppSettingsUpdate
from onboarding.domain.models import WhatsAppBusinessAccount
from shared.deps import CurrentTenant, DbSession
from shared.encryption import encrypt

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


def _to_out(account: WhatsAppBusinessAccount | None) -> WhatsAppSettingsOut:
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


@router.get("/whatsapp", response_model=WhatsAppSettingsOut)
async def get_whatsapp_settings(tenant: CurrentTenant, session: DbSession) -> WhatsAppSettingsOut:
    account = await WhatsAppBusinessAccountRepository(session).get(tenant)
    return _to_out(account)


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
    await session.commit()
    return _to_out(account)
