import logging
from typing import Protocol

import httpx

from shared.config import get_settings

logger = logging.getLogger(__name__)

# WhatsApp Cloud API hard-caps interactive list message row titles at 24
# characters -- a longer title makes Meta reject the *entire* send_list call
# with a 4xx, which _post logs and swallows (returns False) rather than
# raising, so the caller silently gets no reply delivered. Truncating here,
# at the one place that knows this wire-format constraint, protects every
# send_list call site (FAQ menu, FAQ disambiguation list, the greeting menu)
# rather than relying on each caller to remember the limit.
_LIST_ROW_TITLE_MAX_LEN = 24
_LIST_ROW_DESCRIPTION_MAX_LEN = 72


def _list_row(option_id: str, title: str) -> dict[str, str]:
    if len(title) <= _LIST_ROW_TITLE_MAX_LEN:
        return {"id": option_id, "title": title}
    # Title alone can't carry the full text once truncated -- surface it via
    # description too (also capped by Meta, at 72 chars) so e.g. a full FAQ
    # question stays legible instead of just "What are your deliv…".
    truncated_title = title[: _LIST_ROW_TITLE_MAX_LEN - 1].rstrip() + "…"
    return {
        "id": option_id,
        "title": truncated_title,
        "description": title[:_LIST_ROW_DESCRIPTION_MAX_LEN],
    }


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

    async def send_test_message(
        self, *, phone_number_id: str, access_token: str, to: str
    ) -> tuple[bool, str]: ...

    async def send_flow(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        flow_id: str,
        flow_token: str,
        body: str,
        cta: str,
    ) -> bool: ...

    async def send_list(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        body: str,
        button_label: str,
        options: list[tuple[str, str]],  # (id, title)
    ) -> bool: ...

    async def send_cta_url_button(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        body: str,
        display_text: str,
        url: str,
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
            # A 200 only means Meta accepted the request -- it still echoes
            # back the phone number it actually resolved the recipient to
            # (contacts[].wa_id/input), which is worth logging since a
            # mismatch there (wrong number typed at checkout, formatting
            # difference from the number the customer messages from) is a
            # silent, non-erroring delivery failure otherwise invisible here.
            logger.info("WhatsApp send accepted: %s", response.text)
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

    async def send_flow(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        flow_id: str,
        flow_token: str,
        body: str,
        cta: str,
    ) -> bool:
        return await self._post(
            phone_number_id,
            access_token,
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "interactive",
                "interactive": {
                    "type": "flow",
                    "body": {"text": body},
                    "action": {
                        "name": "flow",
                        "parameters": {
                            "flow_message_version": "3",
                            "flow_token": flow_token,
                            "flow_id": flow_id,
                            "flow_cta": cta,
                            # "navigate" renders a purely static screen with no
                            # call to our endpoint at all -- WhatsApp only ever
                            # invokes the data-exchange endpoint's INIT action
                            # (flows/api/router.py) to populate ${data.*} if
                            # the button is sent with "data_exchange" here.
                            "flow_action": "data_exchange",
                        },
                    },
                },
            },
        )

    async def send_cta_url_button(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        body: str,
        display_text: str,
        url: str,
    ) -> bool:
        """Interactive CTA-URL-button message -- BROWSER_LINK mode's
        equivalent of send_flow. Unlike a template message, this needs no
        Meta pre-approval: it's a freeform interactive send, valid within
        the 24h customer-service window every call site here is already
        inside (a reply to an inbound message), same as send_buttons/
        send_list/send_flow above."""
        return await self._post(
            phone_number_id,
            access_token,
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "interactive",
                "interactive": {
                    "type": "cta_url",
                    "body": {"text": body},
                    "action": {
                        "name": "cta_url",
                        "parameters": {"display_text": display_text, "url": url},
                    },
                },
            },
        )

    async def send_list(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        body: str,
        button_label: str,
        options: list[tuple[str, str]],
    ) -> bool:
        """WhatsApp Cloud API's interactive "button" message type is capped
        at 3 buttons by Meta -- once appointment booking or an active FAQ
        pushes the greeting menu past 3 options, it switches to this "list"
        message type instead (send_buttons still covers every merchant
        whose menu stays at 3 options). Also used directly for the FAQ
        menu/disambiguation lists themselves."""
        return await self._post(
            phone_number_id,
            access_token,
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "interactive",
                "interactive": {
                    "type": "list",
                    "body": {"text": body},
                    "action": {
                        "button": button_label,
                        "sections": [
                            {
                                "title": "Options",
                                "rows": [
                                    _list_row(option_id, title) for option_id, title in options
                                ],
                            }
                        ],
                    },
                },
            },
        )

    async def send_test_message(
        self, *, phone_number_id: str, access_token: str, to: str
    ) -> tuple[bool, str]:
        """Send a plain text message to verify saved credentials actually
        work end-to-end. Unlike send_text/send_buttons this reports back
        *why* a send failed, since a "test credentials" button is useless
        if it only ever says no."""
        url = f"{self._base_url}/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": "Orderflow test message - credentials verified!"},
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            if response.status_code == 200:
                return True, "Test message sent successfully"

            error_msg = f"Test message failed: HTTP {response.status_code}"
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", error_msg)
            except ValueError:
                pass
            return False, error_msg
        except httpx.HTTPError as exc:
            logger.warning("WhatsApp test message failed: %s", exc)
            return False, f"Test failed: {exc}"


def get_whatsapp_sender() -> WhatsAppSender:
    """FastAPI dependency provider -- lets tests override with a fake
    sender (app.dependency_overrides) instead of making real HTTP calls
    to graph.facebook.com."""
    return GraphApiWhatsAppSender()
