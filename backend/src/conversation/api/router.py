from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from conversation.adapters.whatsapp_client import WhatsAppSender, get_whatsapp_sender
from conversation.domain.handler import handle_inbound_message
from conversation.domain.webhook_parser import parse_inbound_messages
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
    if hub_mode != "subscribe" or hub_verify_token != settings.whatsapp_webhook_verify_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verification failed")
    return Response(content=hub_challenge, media_type="text/plain")


@router.post("", status_code=status.HTTP_200_OK)
async def receive_webhook(
    request: Request, session: DbSession, sender: WhatsAppSenderDep
) -> dict[str, str]:
    """Always acks 200 to Meta once the payload is parsed, regardless of
    per-message outcome (unknown number, dedupe, send failure) -- Meta
    retries on non-2xx, and none of those outcomes are something a retry
    would fix."""
    payload: Any = await request.json()
    messages = parse_inbound_messages(payload)

    for message in messages:
        await handle_inbound_message(session, sender, message)

    return {"status": "ok"}
