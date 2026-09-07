import hashlib
import hmac
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from campaigns.domain.template_status import apply_template_status_update
from conversation.adapters.whatsapp_client import WhatsAppSender, get_whatsapp_sender
from conversation.domain.handler import handle_inbound_message
from conversation.domain.webhook_parser import parse_inbound_messages, parse_template_status_updates
from shared.config import get_settings
from shared.deps import DbSession

router = APIRouter(prefix="/api/v1/whatsapp/webhook", tags=["conversation"])

WhatsAppSenderDep = Annotated[WhatsAppSender, Depends(get_whatsapp_sender)]


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> Response:
    """Meta's one-time webhook verification handshake, run when the
    webhook URL is first registered in the Meta App dashboard."""
    settings = get_settings()
    if (
        not settings.whatsapp_webhook_verify_token
        or hub_mode != "subscribe"
        or hub_verify_token != settings.whatsapp_webhook_verify_token
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verification failed")
    return Response(content=hub_challenge, media_type="text/plain")


def _verify_signature(body: bytes, signature_header: str | None, app_secret: str | None) -> None:
    """Meta signs every webhook POST with X-Hub-Signature-256 (HMAC-SHA256
    of the raw body, keyed with the Meta App's app secret). Without this,
    anyone who learns/guesses a merchant's phone_number_id could POST an
    arbitrary forged payload -- including a fake WhatsApp Flow order
    submission -- straight into handle_inbound_message with no barrier at
    all. Fails closed: an unconfigured app_secret rejects every POST rather
    than silently skipping verification."""
    if not app_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Webhook signature verification is not configured"
        )
    if not signature_header or not signature_header.startswith("sha256="):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing webhook signature")
    expected = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook signature")


@router.post("", status_code=status.HTTP_200_OK)
async def receive_webhook(
    request: Request, session: DbSession, sender: WhatsAppSenderDep
) -> dict[str, str]:
    """Always acks 200 to Meta once the payload is parsed, regardless of
    per-message outcome (unknown number, dedupe, send failure) -- Meta
    retries on non-2xx, and none of those outcomes are something a retry
    would fix. Signature verification (401/503) is the one thing that
    still short-circuits before that, since an unverified body must never
    reach handle_inbound_message."""
    settings = get_settings()
    body = await request.body()
    _verify_signature(body, request.headers.get("x-hub-signature-256"), settings.meta_app_secret)

    payload: Any = json.loads(body)
    messages = parse_inbound_messages(payload)

    for message in messages:
        await handle_inbound_message(session, sender, message)

    # Meta multiplexes multiple event types onto this one subscribed
    # webhook URL/payload -- template approval/rejection/pause events
    # (campaigns/) arrive here too, not to a separate route. Applied after
    # inbound messages, on the same already-parsed payload/session.
    template_updates = parse_template_status_updates(payload)
    for update in template_updates:
        await apply_template_status_update(session, update)
    if template_updates:
        await session.commit()

    return {"status": "ok"}
