import httpx

from campaigns.domain.models import MessageTemplate
from onboarding.domain.models import WhatsAppBusinessAccount
from shared.config import get_settings
from shared.encryption import decrypt


class TemplateGatewayError(Exception):
    """Wraps whatever Meta's Graph API rejected -- same shape as
    flows/domain/setup.py's FlowSetupError."""

    def __init__(self, step: str, detail: str) -> None:
        super().__init__(f"{step}: {detail}")
        self.step = step
        self.detail = detail


def _base_url() -> str:
    return f"https://graph.facebook.com/{get_settings().meta_graph_api_version}"


def _access_token(waba: WhatsAppBusinessAccount) -> str:
    if not waba.access_token_encrypted:
        raise TemplateGatewayError("precondition", "WhatsApp credentials not configured.")
    return decrypt(waba.access_token_encrypted)


def _build_components(template: MessageTemplate) -> list[dict[str, object]]:
    components: list[dict[str, object]] = []

    if template.header_type == "TEXT":
        components.append({"type": "HEADER", "format": "TEXT", "text": template.header_text})
    elif template.header_type in ("IMAGE", "VIDEO", "DOCUMENT"):
        # Identical wiring for all three media header formats -- Meta's
        # HEADER component only cares about format + example.header_handle
        # here; header_filename (DOCUMENT only) is a send-time concern, not
        # part of the template definition itself.
        components.append(
            {
                "type": "HEADER",
                "format": template.header_type,
                "example": {"header_handle": [template.header_media_handle]},
            }
        )

    body: dict[str, object] = {"type": "BODY", "text": template.body_text}
    if template.body_variable_count > 0:
        # Meta requires a plausible example value per positional variable
        # to review the template against -- a placeholder is sufficient,
        # it isn't what actually renders to customers later.
        body["example"] = {
            "body_text": [[f"example{i + 1}" for i in range(template.body_variable_count)]]
        }
    components.append(body)

    if template.footer_text:
        components.append({"type": "FOOTER", "text": template.footer_text})

    if template.buttons:
        components.append({"type": "BUTTONS", "buttons": template.buttons})

    return components


class MetaTemplateGateway:
    """POST/DELETE /{waba_id}/message_templates using the merchant's own
    WhatsApp access token -- the same per-merchant-token pattern every
    other outbound Meta call in this codebase follows
    (notifications/adapters/whatsapp_channel.py, flows/domain/setup.py).
    Requires WhatsAppBusinessAccount.meta_waba_id, only ever set by
    onboarding/domain/embedded_signup.py -- a merchant connected via the
    legacy manual-paste path (phone_number_id + token only, no WABA id)
    can't submit templates until they reconnect via Embedded Signup."""

    async def create_template(
        self, waba: WhatsAppBusinessAccount, template: MessageTemplate
    ) -> tuple[str, str]:
        """Returns (meta_template_id, initial_status)."""
        if not waba.meta_waba_id:
            raise TemplateGatewayError(
                "precondition", "WhatsApp Business Account ID not on file for this merchant."
            )
        access_token = _access_token(waba)

        payload = {
            "name": template.name,
            "category": template.category,
            "language": template.language_code,
            "components": _build_components(template),
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_base_url()}/{waba.meta_waba_id}/message_templates",
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
            )
        if resp.status_code >= 400:
            raise TemplateGatewayError("create_template", resp.text)

        data = resp.json()
        meta_template_id = data.get("id")
        if not meta_template_id:
            raise TemplateGatewayError("create_template", "Meta returned no template id.")
        # Meta returns "status" (usually "PENDING") on a successful create --
        # lowercased to match MessageTemplate.meta_approval_status's values.
        status = str(data.get("status", "PENDING")).lower()
        return str(meta_template_id), status

    async def delete_template(self, waba: WhatsAppBusinessAccount, meta_template_id: str) -> None:
        """DELETE /{waba_id}/message_templates?hsm_id={id} -- called before
        the local row is removed, mirroring flows/domain/setup.py's
        "durable state matches Meta's, in that order" discipline."""
        if not waba.meta_waba_id:
            raise TemplateGatewayError(
                "precondition", "WhatsApp Business Account ID not on file for this merchant."
            )
        access_token = _access_token(waba)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{_base_url()}/{waba.meta_waba_id}/message_templates",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"hsm_id": meta_template_id},
            )
        if resp.status_code >= 400:
            raise TemplateGatewayError("delete_template", resp.text)
