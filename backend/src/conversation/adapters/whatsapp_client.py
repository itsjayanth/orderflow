import logging
from typing import Protocol

import httpx

from shared.config import get_settings

logger = logging.getLogger(__name__)


class WhatsAppSender(Protocol):
    async def send_text(
        self, *, phone_number_id: str, access_token: str, to: str, body: str
    ) -> bool: ...

    async def send_buttons(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        body: str,
        buttons: list[tuple[str, str]],  # (id, title)
    ) -> bool: ...


class GraphApiWhatsAppSender:
    """Real WhatsApp Cloud API client. Every call is best-effort: a failed
    send (no live WABA behind the merchant's dummy credentials, an
    expired token, a network error) is logged and returns False rather
    than raising, so the Conversation Handler can always finish
    processing and ack the inbound webhook to Meta -- delivery failure
    for our reply is a notification-layer concern, not a webhook-handling
    one. This means the whole inbound side (tenant resolution, dedupe,
    intent routing, order creation) is fully exercisable without a live
    Meta connection; only the actual outbound delivery no-ops until real
    credentials are on file."""

    def __init__(self) -> None:
        self._base_url = get_settings().whatsapp_graph_api_base_url

    async def _post(
        self, phone_number_id: str, access_token: str, payload: dict[str, object]
    ) -> bool:
        url = f"{self._base_url}/{phone_number_id}/messages"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            if response.status_code >= 400:
                logger.warning(
                    "WhatsApp send failed (status=%s): %s", response.status_code, response.text
                )
                return False
            return True
        except httpx.HTTPError as exc:
            logger.warning("WhatsApp send failed: %s", exc)
            return False

    async def send_text(
        self, *, phone_number_id: str, access_token: str, to: str, body: str
    ) -> bool:
        return await self._post(
            phone_number_id,
            access_token,
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": body},
            },
        )

    async def send_buttons(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        body: str,
        buttons: list[tuple[str, str]],
    ) -> bool:
        return await self._post(
            phone_number_id,
            access_token,
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": body},
                    "action": {
                        "buttons": [
                            {"type": "reply", "reply": {"id": button_id, "title": title}}
                            for button_id, title in buttons
                        ]
                    },
                },
            },
        )


def get_whatsapp_sender() -> WhatsAppSender:
    """FastAPI dependency provider -- lets tests override with a fake
    sender (app.dependency_overrides) instead of making real HTTP calls
    to graph.facebook.com."""
    return GraphApiWhatsAppSender()
