from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from flows.domain.encryption import generate_key_pair
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from onboarding.domain.models import WhatsAppBusinessAccount
from shared.config import get_settings
from shared.encryption import decrypt, encrypt
from shared.tenant import TenantContext

_FLOW_JSON_PATH = Path(__file__).resolve().parent.parent / "assets" / "order_flow.json"


class FlowSetupError(Exception):
    """Wraps whatever Meta's API rejected, with which step failed -- so a
    caller (CLI script or the dashboard endpoint) can show something more
    useful than a raw httpx traceback."""

    def __init__(self, step: str, detail: str) -> None:
        super().__init__(f"{step}: {detail}")
        self.step = step
        self.detail = detail


async def upload_flow_json(
    client: httpx.AsyncClient, base_url: str, flow_id: str, headers: dict[str, str]
) -> None:
    """Uploads the current order_flow.json as the given Flow's FLOW_JSON
    asset. Factored out of setup_whatsapp_flow() so update_flow_assets()
    (pushing an updated JSON to a merchant who already has a flow_id) can
    share the exact same upload call instead of duplicating it."""
    resp = await client.post(
        f"{base_url}/{flow_id}/assets",
        headers=headers,
        data={"name": "flow.json", "asset_type": "FLOW_JSON"},
        files={"file": ("flow.json", _FLOW_JSON_PATH.read_bytes(), "application/json")},
    )
    if resp.status_code >= 400:
        raise FlowSetupError("upload_flow_json", resp.text)


async def setup_whatsapp_flow(
    session: AsyncSession,
    tenant: TenantContext,
    waba: WhatsAppBusinessAccount,
    *,
    meta_waba_id: str,
    backend_base_url: str,
) -> str:
    """One-time per-merchant setup for native WhatsApp ordering, shared by
    scripts/setup_whatsapp_flow.py (run from a developer's machine) and
    onboarding/api/router.py's authenticated endpoint (run from inside the
    deployed app, where real credentials already exist in the process
    environment -- no secrets need to leave Railway to make this work).
    Returns the created flow_id; also persists it + the encrypted RSA
    private key onto the merchant's WhatsAppBusinessAccount row."""
    if not waba.phone_number_id or not waba.access_token_encrypted:
        raise FlowSetupError("precondition", "WhatsApp credentials not configured")

    base_url = get_settings().whatsapp_graph_api_base_url
    access_token = decrypt(waba.access_token_encrypted)
    headers = {"Authorization": f"Bearer {access_token}"}

    public_pem, private_pem = generate_key_pair()

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base_url}/{waba.phone_number_id}/whatsapp_business_encryption",
            headers=headers,
            data={"business_public_key": public_pem},
        )
        if resp.status_code >= 400:
            raise FlowSetupError("upload_public_key", resp.text)

        endpoint_uri = (
            f"{backend_base_url.rstrip('/')}/api/v1/whatsapp/flows/{tenant.merchant_id}/data-exchange"
        )
        resp = await client.post(
            f"{base_url}/{meta_waba_id}/flows",
            headers=headers,
            json={
                "name": "Order via WhatsApp",
                "categories": ["OTHER"],
                "endpoint_uri": endpoint_uri,
            },
        )
        if resp.status_code >= 400:
            raise FlowSetupError("create_flow", resp.text)
        flow_id = resp.json()["id"]

        # Persisted the moment we have a flow_id, *before* JSON upload/
        # publish -- Meta can start pinging endpoint_uri for its
        # pre-publish health check as soon as the Flow exists, and if that
        # happens before this function returns, our endpoint needs the
        # private key on file to answer it. It also means a failure in a
        # later step (as originally happened here -- publish failing
        # before credentials were ever saved, silently discarding a
        # generated key Meta had already accepted) doesn't strand an
        # orphaned Flow with no way to retry against the same key pair.
        await WhatsAppBusinessAccountRepository(session).set_flow_credentials(
            tenant, flow_id=flow_id, private_key_encrypted=encrypt(private_pem)
        )
        await session.commit()

        await upload_flow_json(client, base_url, flow_id, headers)

        resp = await client.post(f"{base_url}/{flow_id}/publish", headers=headers)
        if resp.status_code >= 400:
            raise FlowSetupError("publish_flow", resp.text)

    return str(flow_id)


async def update_flow_assets(
    session: AsyncSession, tenant: TenantContext, waba: WhatsAppBusinessAccount
) -> None:
    """Pushes the current order_flow.json to Meta for a merchant who
    already ran setup_whatsapp_flow() once -- e.g. after the Flow JSON
    itself changes (new screens/fields, like the DETAILS screen's name/
    contact/address-choice additions) and an already-onboarded merchant's
    Flow needs the update, without recreating the whole Flow (new flow_id,
    new RSA key pair) from scratch. session/tenant aren't used for a DB
    write here (there's nothing new to persist -- flow_id and the private
    key are unchanged), but are accepted for symmetry with
    setup_whatsapp_flow() and so a future caller doesn't need to change
    the signature to add one.

    Uploading assets to an already-published Flow resets its status to
    DRAFT (confirmed empirically via get_flow_validation() -- Meta doesn't
    document this clearly) -- so this also re-publishes, the same call
    setup_whatsapp_flow() makes for a brand-new Flow, or the update would
    silently sit as an unpublished draft with the live Flow potentially
    still serving whatever was published before."""
    if not waba.whatsapp_flow_id:
        raise FlowSetupError("precondition", "Flow not set up for this merchant yet")
    if not waba.access_token_encrypted:
        raise FlowSetupError("precondition", "WhatsApp credentials not configured")

    base_url = get_settings().whatsapp_graph_api_base_url
    access_token = decrypt(waba.access_token_encrypted)
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        await upload_flow_json(client, base_url, waba.whatsapp_flow_id, headers)

        resp = await client.post(f"{base_url}/{waba.whatsapp_flow_id}/publish", headers=headers)
        if resp.status_code >= 400:
            raise FlowSetupError("publish_flow", resp.text)


async def get_flow_validation(waba: WhatsAppBusinessAccount) -> dict[str, object]:
    """Reads back the Flow's current status/validation_errors/health_status
    from Meta -- a successful (<400) response from upload_flow_json()/
    /assets only means Meta *accepted the upload*, not that the JSON is
    actually valid; structural problems (bad expressions, a field
    reference that doesn't resolve, etc.) show up here instead, the same
    place Meta's own publish-time health check would have caught them.
    Called right after update_flow_assets() so a broken update is visible
    immediately rather than only discovered via a customer's broken
    in-chat experience."""
    if not waba.whatsapp_flow_id:
        raise FlowSetupError("precondition", "Flow not set up for this merchant yet")
    if not waba.access_token_encrypted:
        raise FlowSetupError("precondition", "WhatsApp credentials not configured")

    base_url = get_settings().whatsapp_graph_api_base_url
    access_token = decrypt(waba.access_token_encrypted)
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{base_url}/{waba.whatsapp_flow_id}",
            headers=headers,
            params={"fields": "status,validation_errors,health_status"},
        )
    if resp.status_code >= 400:
        raise FlowSetupError("get_flow_validation", resp.text)
    return dict(resp.json())
