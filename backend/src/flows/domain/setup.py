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

        resp = await client.post(
            f"{base_url}/{flow_id}/assets",
            headers=headers,
            data={"name": "flow.json", "asset_type": "FLOW_JSON"},
            files={"file": ("flow.json", _FLOW_JSON_PATH.read_bytes(), "application/json")},
        )
        if resp.status_code >= 400:
            raise FlowSetupError("upload_flow_json", resp.text)

        resp = await client.post(f"{base_url}/{flow_id}/publish", headers=headers)
        if resp.status_code >= 400:
            raise FlowSetupError("publish_flow", resp.text)

    await WhatsAppBusinessAccountRepository(session).set_flow_credentials(
        tenant, flow_id=flow_id, private_key_encrypted=encrypt(private_pem)
    )
    return str(flow_id)
