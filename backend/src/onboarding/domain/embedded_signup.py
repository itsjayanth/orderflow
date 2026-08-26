import datetime
import secrets

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from onboarding.domain.models import WhatsAppBusinessAccount
from onboarding.domain.onboarding_service import advance_after_whatsapp_connected
from shared.config import get_settings
from shared.encryption import encrypt
from shared.tenant import TenantContext


class EmbeddedSignupError(Exception):
    """Wraps whatever Meta's API rejected during the Embedded Signup
    handshake, with which step failed -- same pattern as
    flows/domain/setup.py's FlowSetupError, so the router can report
    something more useful than a raw httpx traceback."""

    def __init__(self, step: str, detail: str) -> None:
        super().__init__(f"{step}: {detail}")
        self.step = step
        self.detail = detail


def embedded_signup_configured() -> bool:
    """Whether the app-level Meta credentials needed to run Embedded
    Signup are present -- the manual paste flow works without any of
    these, so a fresh deployment shouldn't be blocked on them."""
    settings = get_settings()
    return bool(
        settings.meta_app_id and settings.meta_app_secret and settings.meta_configuration_id
    )


async def complete_embedded_signup(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    code: str,
    waba_id: str,
    phone_number_id: str,
) -> WhatsAppBusinessAccount:
    """Runs after the frontend's Facebook Login for Business popup finishes:
    exchanges the short-lived `code` the JS SDK returned for a long-lived
    system-user access token, registers the phone number for API messaging
    (required once per number before it can send/receive at all), subscribes
    our app to the WABA's webhooks, then persists everything onto the same
    WhatsAppBusinessAccount row the manual flow writes -- so every other
    module (conversation, notifications, flows) keeps working unchanged."""
    settings = get_settings()
    if not settings.meta_app_id or not settings.meta_app_secret:
        raise EmbeddedSignupError(
            "precondition", "Embedded Signup is not configured on this server"
        )

    base_url = f"https://graph.facebook.com/{settings.meta_graph_api_version}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        token_resp = await client.get(
            f"{base_url}/oauth/access_token",
            params={
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "code": code,
            },
        )
        if token_resp.status_code >= 400:
            raise EmbeddedSignupError("exchange_code", token_resp.text)
        token_body = token_resp.json()
        access_token = token_body.get("access_token")
        if not access_token:
            raise EmbeddedSignupError("exchange_code", token_resp.text)

        token_expiry_at: datetime.datetime | None = None
        expires_in = token_body.get("expires_in")
        if isinstance(expires_in, int) and expires_in > 0:
            token_expiry_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
                seconds=expires_in
            )

        headers = {"Authorization": f"Bearer {access_token}"}

        display_phone_number: str | None = None
        phone_resp = await client.get(
            f"{base_url}/{phone_number_id}",
            headers=headers,
            params={"fields": "display_phone_number"},
        )
        if phone_resp.status_code < 400:
            display_phone_number = phone_resp.json().get("display_phone_number")

        # Required once per number before it can send/receive via the API
        # at all -- without this the number stays visible on the WABA but
        # every send call 4xxs. Meta requires a 6-digit PIN for two-step
        # verification; keep it on file since re-registration (e.g. after
        # a migration) needs the same PIN again.
        two_step_pin = f"{secrets.randbelow(1_000_000):06d}"
        register_resp = await client.post(
            f"{base_url}/{phone_number_id}/register",
            headers=headers,
            json={"messaging_product": "whatsapp", "pin": two_step_pin},
        )
        if register_resp.status_code >= 400:
            raise EmbeddedSignupError("register_phone_number", register_resp.text)

        subscribe_resp = await client.post(
            f"{base_url}/{waba_id}/subscribed_apps",
            headers=headers,
        )
        if subscribe_resp.status_code >= 400:
            raise EmbeddedSignupError("subscribe_webhooks", subscribe_resp.text)

    account = await WhatsAppBusinessAccountRepository(session).upsert_from_embedded_signup(
        tenant,
        phone_number_id=phone_number_id,
        meta_waba_id=waba_id,
        access_token_encrypted=encrypt(access_token),
        display_phone_number=display_phone_number,
        token_expiry_at=token_expiry_at,
        two_step_pin_encrypted=encrypt(two_step_pin),
    )
    await advance_after_whatsapp_connected(session, tenant)
    return account
