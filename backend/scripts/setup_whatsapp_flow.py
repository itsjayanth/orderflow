"""One-time, per-merchant setup for native WhatsApp ordering (see backend/src/flows/).

Generates an RSA key pair, uploads the public half to Meta for this
merchant's phone number, creates+uploads+publishes the "Order via
WhatsApp" Flow against this app's data-exchange endpoint, and stores the
Flow id + encrypted private key on the merchant's WhatsAppBusinessAccount
row. Run once per merchant after they've connected WhatsApp credentials
in Settings; conversation/domain/handler.py automatically starts sending
the Flow (instead of the webview link) for PLACE_ORDER the moment
whatsapp_flow_id is set.

Usage (from backend/, with the merchant's WABA already connected in Settings):

    uv run python scripts/setup_whatsapp_flow.py \\
        --merchant-id <uuid> \\
        --meta-waba-id <the WhatsApp Business Account ID shown in Meta's API Setup page> \\
        --backend-base-url https://orderflow-api-sandbox.up.railway.app

--meta-waba-id isn't stored anywhere in orderflow today (onboarding only
captures phone_number_id + access_token, see onboarding/adapters/repository.py's
upsert) -- find it on Meta's "API Setup" page for the app, next to "WhatsApp
Business Account ID".
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from flows.domain.encryption import generate_key_pair  # noqa: E402
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository  # noqa: E402
from shared.config import get_settings  # noqa: E402
from shared.db import SessionFactory  # noqa: E402
from shared.encryption import decrypt, encrypt  # noqa: E402
from shared.tenant import TenantContext  # noqa: E402

_FLOW_JSON_PATH = (
    Path(__file__).resolve().parent.parent / "src" / "flows" / "assets" / "order_flow.json"
)


async def main(*, merchant_id: uuid.UUID, meta_waba_id: str, backend_base_url: str) -> None:
    settings = get_settings()
    base_url = settings.whatsapp_graph_api_base_url

    async with SessionFactory() as session:
        tenant = TenantContext(merchant_id=merchant_id)
        waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
        if waba is None or not waba.phone_number_id or not waba.access_token_encrypted:
            raise SystemExit(
                f"Merchant {merchant_id} has no WhatsApp credentials on file -- "
                "connect WhatsApp in Settings first."
            )

        access_token = decrypt(waba.access_token_encrypted)
        phone_number_id = waba.phone_number_id

    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {access_token}"}

        print("Generating RSA key pair...")
        public_pem, private_pem = generate_key_pair()

        print(f"Uploading public key to phone number {phone_number_id}...")
        resp = await client.post(
            f"{base_url}/{phone_number_id}/whatsapp_business_encryption",
            headers=headers,
            data={"business_public_key": public_pem},
        )
        resp.raise_for_status()
        print(f"  -> {resp.json()}")

        endpoint_uri = (
            f"{backend_base_url.rstrip('/')}/api/v1/whatsapp/flows/{merchant_id}/data-exchange"
        )
        print(f"Creating Flow (endpoint_uri={endpoint_uri})...")
        resp = await client.post(
            f"{base_url}/{meta_waba_id}/flows",
            headers=headers,
            json={
                "name": "Order via WhatsApp",
                "categories": ["OTHER"],
                "endpoint_uri": endpoint_uri,
            },
        )
        resp.raise_for_status()
        flow_id = resp.json()["id"]
        print(f"  -> flow_id={flow_id}")

        print("Uploading Flow JSON...")
        flow_json_bytes = _FLOW_JSON_PATH.read_bytes()
        resp = await client.post(
            f"{base_url}/{flow_id}/assets",
            headers=headers,
            data={"name": "flow.json", "asset_type": "FLOW_JSON"},
            files={"file": ("flow.json", flow_json_bytes, "application/json")},
        )
        resp.raise_for_status()
        print(f"  -> {resp.json()}")

        print("Publishing Flow...")
        resp = await client.post(f"{base_url}/{flow_id}/publish", headers=headers)
        resp.raise_for_status()
        print(f"  -> {resp.json()}")

    async with SessionFactory() as session:
        await WhatsAppBusinessAccountRepository(session).set_flow_credentials(
            tenant, flow_id=flow_id, private_key_encrypted=encrypt(private_pem)
        )
        await session.commit()

    print(f'\nDone. Merchant {merchant_id} now sends the native Flow for "place order".')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--merchant-id", required=True, type=uuid.UUID)
    parser.add_argument("--meta-waba-id", required=True)
    parser.add_argument("--backend-base-url", required=True)
    args = parser.parse_args()

    asyncio.run(
        main(
            merchant_id=args.merchant_id,
            meta_waba_id=args.meta_waba_id,
            backend_base_url=args.backend_base_url,
        )
    )
