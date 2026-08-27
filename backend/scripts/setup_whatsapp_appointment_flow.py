"""One-time, per-merchant setup for native WhatsApp appointment booking (see backend/src/flows/).

Generates a fresh RSA key pair, uploads the public half to Meta for this
merchant's phone number, creates+uploads+publishes the "Book an
Appointment" Flow against this app's appointment-data-exchange endpoint,
and stores the Flow id + encrypted private key on the merchant's
WhatsAppBusinessAccount row. Run once per merchant after they've
connected WhatsApp credentials in Settings and enabled appointment
booking; conversation/domain/handler.py automatically starts sending the
Flow (instead of the webview link) for appointment booking the moment
whatsapp_appointment_flow_id is set.

This is the CLI form -- flows/domain/setup.py's
setup_whatsapp_appointment_flow is the actual logic, shared with
onboarding/api/router.py's authenticated POST
/api/v1/onboarding/whatsapp/appointment-flow-setup endpoint (the one to
prefer when running against a deployed environment, since it runs inside
that environment with real credentials already in place -- no secrets
need to leave Railway to make this work). This CLI form needs
DATABASE_URL and SECRETS_ENCRYPTION_KEY in the local .env to match
whatever environment's WABA row it's pointed at.

Usage (from backend/, with the merchant's WABA already connected in Settings):

    uv run python scripts/setup_whatsapp_appointment_flow.py \\
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from flows.domain.setup import FlowSetupError, setup_whatsapp_appointment_flow  # noqa: E402
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository  # noqa: E402
from shared.db import SessionFactory  # noqa: E402
from shared.tenant import TenantContext  # noqa: E402


async def main(*, merchant_id: uuid.UUID, meta_waba_id: str, backend_base_url: str) -> None:
    tenant = TenantContext(merchant_id=merchant_id)

    async with SessionFactory() as session:
        waba = await WhatsAppBusinessAccountRepository(session).get(tenant)
        if waba is None:
            raise SystemExit(
                f"Merchant {merchant_id} has no WhatsApp credentials on file -- "
                "connect WhatsApp in Settings first."
            )

        print("Setting up WhatsApp appointment Flow (uploading key, creating + publishing Flow)...")
        try:
            flow_id = await setup_whatsapp_appointment_flow(
                session,
                tenant,
                waba,
                meta_waba_id=meta_waba_id,
                backend_base_url=backend_base_url,
            )
        except FlowSetupError as exc:
            raise SystemExit(f"Failed at step '{exc.step}': {exc.detail}") from exc

        await session.commit()

    print(
        f'\nDone (flow_id={flow_id}). Merchant {merchant_id} now sends the native Flow '
        'for appointment booking.'
    )


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
