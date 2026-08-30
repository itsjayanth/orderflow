import secrets
from dataclasses import dataclass, field

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from shared.config import get_settings
from shared.encryption import encrypt
from shared.tenant import TenantContext

"""Server half of Meta's WhatsApp Embedded Signup flow -- replaces the
manual "paste phone_number_id + access_token" onboarding path with a
single "Connect your WhatsApp Business account" button. The browser popup
(frontend/src/features/onboarding/useEmbeddedSignup.ts) hands this module a
short-lived authorization `code` plus the waba_id/phone_number_id the
merchant just created or selected, and the session `event` that terminated
the popup.

Ported from FastFlow's Phase 7 reference implementation
(fastflow/backend/app/services/meta_onboarding_service.py) -- same shape
(event dispatch before any Meta call, code exchange, token verification,
persist, then best-effort deferred Meta-side setup that never rolls back
already-committed credentials) but trimmed to what orderflow actually
needs: no Coexistence handling (orderflow never offered the WhatsApp
Business App migration path fastflow's BYOT merchants needed) and no
phone-number-mismatch pending-orders check (that guards against
overwriting credentials mid-flight for a store with in-flight COD
Confirm/Cancel replies tied to the old number -- a fastflow-specific
concern; orderflow's WhatsAppBusinessAccount is a single row per merchant
with no equivalent state to strand).

Reuses fastflow's Meta App ("OrdzoLive", meta_app_id, decided 2026-08-30)
rather than a dedicated one, via a separate Facebook Login for Business
configuration ("Orderflow Embedded Signup") scoped to orderflow's own
domain -- see shared/config.py's meta_app_id docstring. Because the Meta
App is shared, _subscribe_app_to_waba MUST pass orderflow's own
override_callback_uri (built from backend_base_url below); relying on the
app's default Callback URL would route orderflow's webhook events to
fastflow's backend instead."""

EVENT_FINISH = "FINISH"
EVENT_FINISH_ONLY_WABA = "FINISH_ONLY_WABA"
_PROCEEDING_EVENTS = frozenset({EVENT_FINISH, EVENT_FINISH_ONLY_WABA})

_WABA_MANAGEMENT_SCOPE = "whatsapp_business_management"

STATUS_CONNECTED = "connected"
STATUS_NOT_COMPLETED = "not_completed"


class EmbeddedSignupError(Exception):
    """Wraps whatever Meta's API rejected, with which step failed and
    whether re-running the popup can fix it -- same shape as
    flows/domain/setup.py's FlowSetupError, so the router can map both the
    same way, but adds `retryable` since a merchant-driven retry (re-run
    the popup) is the actual remedy for a dead code, unlike a Flow setup
    failure."""

    def __init__(self, step: str, detail: str, *, retryable: bool = True) -> None:
        super().__init__(f"{step}: {detail}")
        self.step = step
        self.detail = detail
        self.retryable = retryable


@dataclass
class EmbeddedSignupResult:
    status: str  # STATUS_CONNECTED | STATUS_NOT_COMPLETED
    message: str
    phone_number_id: str | None = None
    display_phone_number: str | None = None
    connection_status: str | None = None
    # Best-effort Meta-side steps (WABA webhook subscription, phone
    # registration) that failed but didn't block persisting credentials --
    # named here so a merchant/support can see what still needs a retry,
    # same reasoning as fastflow's `pending_steps`.
    pending_steps: list[str] = field(default_factory=list)


def _require_app_credentials() -> tuple[str, str]:
    settings = get_settings()
    if not settings.meta_app_id or not settings.meta_app_secret:
        raise EmbeddedSignupError(
            "precondition",
            "META_APP_ID/META_APP_SECRET are not configured on this deployment.",
            retryable=False,
        )
    return settings.meta_app_id, settings.meta_app_secret


def _base_url() -> str:
    return f"https://graph.facebook.com/{get_settings().meta_graph_api_version}"


async def _exchange_code_for_token(client: httpx.AsyncClient, code: str) -> str:
    app_id, app_secret = _require_app_credentials()
    resp = await client.get(
        f"{_base_url()}/oauth/access_token",
        params={"client_id": app_id, "client_secret": app_secret, "code": code},
    )
    try:
        data = resp.json()
    except ValueError as exc:
        raise EmbeddedSignupError(
            "code_exchange", "Meta returned an unparseable response.", retryable=True
        ) from exc
    if resp.status_code >= 400 or "error" in data or "access_token" not in data:
        err = (data.get("error") or {}).get("message", resp.text)
        raise EmbeddedSignupError("code_exchange", err, retryable=True)
    return str(data["access_token"])


async def _verify_waba_scope(client: httpx.AsyncClient, access_token: str, waba_id: str) -> None:
    """Confirms the freshly minted token can actually act on `waba_id`
    before anything is written -- an exchange succeeding only proves Meta
    minted *a* token, not that it covers the WABA the merchant just told
    us about. A half-configured account (token saved, but for the wrong
    WABA) fails silently on every future send; failing loudly here instead
    is the same trade fastflow's `_assert_waba_in_granular_scopes` makes."""
    app_id, app_secret = _require_app_credentials()
    resp = await client.get(
        f"{_base_url()}/debug_token",
        params={"input_token": access_token, "access_token": f"{app_id}|{app_secret}"},
    )
    try:
        data = (resp.json() or {}).get("data", {}) or {}
    except ValueError:
        data = {}
    if resp.status_code >= 400 or not data.get("is_valid"):
        raise EmbeddedSignupError(
            "verify_token", "Meta reported the new access token as invalid.", retryable=True
        )
    granular = data.get("granular_scopes") or []
    covers_waba = any(
        scope.get("scope") == _WABA_MANAGEMENT_SCOPE and waba_id in (scope.get("target_ids") or [])
        for scope in granular
    )
    if not covers_waba:
        raise EmbeddedSignupError(
            "verify_token",
            "The granted token does not cover the selected WhatsApp Business Account.",
            retryable=True,
        )


async def _fetch_display_phone_number(
    client: httpx.AsyncClient, access_token: str, phone_number_id: str
) -> str | None:
    """Best-effort -- shown in the UI but never blocks onboarding if it
    fails (e.g. the token doesn't (yet) have phone-number-level read
    access)."""
    try:
        resp = await client.get(
            f"{_base_url()}/{phone_number_id}",
            params={"fields": "display_phone_number"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code >= 400:
            return None
        value = resp.json().get("display_phone_number")
        return str(value) if value is not None else None
    except (httpx.HTTPError, ValueError):
        return None


async def _subscribe_app_to_waba(
    client: httpx.AsyncClient,
    access_token: str,
    waba_id: str,
    *,
    override_callback_uri: str | None = None,
    verify_token: str | None = None,
) -> bool:
    """`POST /{waba_id}/subscribed_apps`. The Meta App backing this
    (OrdzoLive, shared with fastflow -- see shared/config.py's meta_app_id
    docstring) has its own app-level default Callback URL, which is
    fastflow's endpoint, not orderflow's. Without `override_callback_uri`,
    a WABA subscribed here would send its webhook events to fastflow's
    backend instead of orderflow's -- so, unlike a dedicated single-tenant
    app, this call MUST pass orderflow's own callback URL explicitly, the
    same reason fastflow's own `subscribe_app_to_waba` takes one per-store.
    `verify_token` must match what's checked by `whatsapp_webhook_verify_token`
    on orderflow's `GET /api/v1/whatsapp/webhook` handshake."""
    try:
        payload: dict[str, str] = {}
        if override_callback_uri is not None:
            payload["override_callback_uri"] = override_callback_uri
        if verify_token is not None:
            payload["verify_token"] = verify_token
        resp = await client.post(
            f"{_base_url()}/{waba_id}/subscribed_apps",
            headers={"Authorization": f"Bearer {access_token}"},
            json=payload or None,
        )
        return resp.status_code == 200 and bool(resp.json().get("success"))
    except (httpx.HTTPError, ValueError):
        return False


_ALREADY_REGISTERED_MARKERS = ("already registered", "already been registered")


async def _register_phone_number(
    client: httpx.AsyncClient, access_token: str, phone_number_id: str, pin: str
) -> bool:
    """`POST /{phone_number_id}/register` -- required before the number can
    send/receive via the Cloud API at all. Treats Meta's "already
    registered" error as success (matching fastflow's convention) so a
    merchant re-running the connect flow, or a retry after this step
    failed the first time, doesn't get stuck."""
    try:
        resp = await client.post(
            f"{_base_url()}/{phone_number_id}/register",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"messaging_product": "whatsapp", "pin": pin},
        )
        if resp.status_code == 200:
            try:
                if resp.json().get("success"):
                    return True
            except ValueError:
                pass
        message = ""
        try:
            message = ((resp.json().get("error") or {}).get("message") or "").lower()
        except ValueError:
            pass
        return any(marker in message for marker in _ALREADY_REGISTERED_MARKERS)
    except httpx.HTTPError:
        return False


async def complete_embedded_signup(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    code: str | None,
    waba_id: str | None,
    phone_number_id: str | None = None,
    business_id: str | None = None,
    event: str = EVENT_FINISH,
    backend_base_url: str | None = None,
) -> EmbeddedSignupResult:
    """Runs the Embedded Signup orchestration for `tenant` -- does not
    commit; the router commits, same convention as every other onboarding
    endpoint (see onboarding/api/router.py's update_whatsapp_settings).
    `backend_base_url` is this deployment's own public URL (the frontend
    passes `import.meta.env.VITE_API_URL`, same convention as
    WhatsAppFlowSetupRequest.backend_base_url) -- used to build the
    `override_callback_uri` the WABA subscription needs; see
    _subscribe_app_to_waba's docstring for why that's required now that
    orderflow shares a Meta App with fastflow."""
    normalized_event = (event or "").strip().upper() or EVENT_FINISH

    if normalized_event not in _PROCEEDING_EVENTS:
        # CANCEL, or an unrecognized/unsupported event (e.g. the
        # Coexistence terminal event fastflow handles specially -- orderflow
        # never supported that path, so it's treated the same as a plain
        # cancel here): nothing changed, not an error.
        return EmbeddedSignupResult(
            status=STATUS_NOT_COMPLETED,
            message=(
                "WhatsApp signup was not completed. Nothing was changed -- "
                "start the connection again when you're ready."
            ),
        )

    if not code:
        raise EmbeddedSignupError(
            "precondition", "Missing authorization code from Meta.", retryable=True
        )
    if not waba_id:
        raise EmbeddedSignupError(
            "precondition", "Missing WhatsApp Business Account ID from Meta.", retryable=True
        )

    pending_steps: list[str] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        access_token = await _exchange_code_for_token(client, code)
        await _verify_waba_scope(client, access_token, waba_id)

        resolved_phone_number_id = phone_number_id if normalized_event == EVENT_FINISH else None
        display_phone_number = None
        if resolved_phone_number_id:
            display_phone_number = await _fetch_display_phone_number(
                client, access_token, resolved_phone_number_id
            )

        # Persisted before the deferred steps below, mirroring
        # flows/domain/setup.py's "save as soon as we have something
        # durable" discipline -- a failure in webhook subscription or
        # phone registration must not discard a verified, working token.
        registration_pin = secrets.token_hex(3)  # 6 hex chars, stand-in numeric-ish PIN
        account = await WhatsAppBusinessAccountRepository(session).upsert_from_embedded_signup(
            tenant,
            meta_waba_id=waba_id,
            phone_number_id=resolved_phone_number_id,
            display_phone_number=display_phone_number,
            access_token_encrypted=encrypt(access_token),
            registration_pin_encrypted=(
                encrypt(registration_pin) if resolved_phone_number_id else None
            ),
        )
        await session.flush()

        override_callback_uri = (
            f"{backend_base_url.rstrip('/')}/api/v1/whatsapp/webhook" if backend_base_url else None
        )
        verify_token = get_settings().whatsapp_webhook_verify_token if backend_base_url else None
        if await _subscribe_app_to_waba(
            client,
            access_token,
            waba_id,
            override_callback_uri=override_callback_uri,
            verify_token=verify_token,
        ):
            await WhatsAppBusinessAccountRepository(session).mark_webhook_subscribed(tenant)
        else:
            pending_steps.append("webhook_subscription")

        if resolved_phone_number_id:
            if not await _register_phone_number(
                client, access_token, resolved_phone_number_id, registration_pin
            ):
                pending_steps.append("phone_number_registration")

    return EmbeddedSignupResult(
        status=STATUS_CONNECTED,
        message="WhatsApp connected.",
        phone_number_id=account.phone_number_id,
        display_phone_number=account.display_phone_number,
        connection_status=account.connection_status,
        pending_steps=pending_steps,
    )
