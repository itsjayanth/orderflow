import httpx

from onboarding.domain.models import WhatsAppBusinessAccount
from shared.config import get_settings
from shared.encryption import decrypt

# Phase 13 scope: image headers only. Phase 16 widens _ALLOWED_CONTENT_TYPES/
# _MAX_SIZE_BYTES per media kind and renames this to upload_header_media --
# the Resumable Upload call itself (this function's body) doesn't change,
# since Meta's upload API is media-type-agnostic at that layer. Keeping the
# signature as (raw bytes + content type in, an opaque handle string out)
# now is what makes that later widening a small change, not new plumbing.
_MAX_SIZE_BYTES = 5 * 1024 * 1024  # Meta's documented cap for an IMAGE header example
_ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png"})


class MediaUploadError(Exception):
    """Wraps whatever Meta's Resumable Upload API rejected -- same shape as
    flows/domain/setup.py's FlowSetupError and onboarding/domain/
    embedded_signup.py's EmbeddedSignupError."""

    def __init__(self, step: str, detail: str) -> None:
        super().__init__(f"{step}: {detail}")
        self.step = step
        self.detail = detail


def _base_url() -> str:
    return f"https://graph.facebook.com/{get_settings().meta_graph_api_version}"


async def upload_header_image(
    waba: WhatsAppBusinessAccount, image_bytes: bytes, content_type: str
) -> str:
    """Meta's Resumable Upload API: POST /{app_id}/uploads starts a session,
    then POST /{upload_session_id} streams the bytes to get back an opaque
    header_handle -- the string a template's HEADER component's
    example.header_handle field needs at submission time
    (campaigns/adapters/template_gateway.py). Authenticated with the
    merchant's own WhatsApp access token (already verified to cover
    whatsapp_business_management by onboarding/domain/embedded_signup.py's
    _verify_waba_scope), the same per-merchant-token convention every
    other outbound Meta call in this codebase follows -- not a separate
    app-level credential."""
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise MediaUploadError(
            "precondition", f"Unsupported image type {content_type!r} for a template header."
        )
    if len(image_bytes) > _MAX_SIZE_BYTES:
        raise MediaUploadError(
            "precondition", f"Image header must be at most {_MAX_SIZE_BYTES} bytes."
        )

    settings = get_settings()
    if not settings.meta_app_id:
        raise MediaUploadError("precondition", "META_APP_ID is not configured on this deployment.")
    if not waba.access_token_encrypted:
        raise MediaUploadError("precondition", "WhatsApp credentials not configured.")
    access_token = decrypt(waba.access_token_encrypted)

    async with httpx.AsyncClient(timeout=30.0) as client:
        start_resp = await client.post(
            f"{_base_url()}/{settings.meta_app_id}/uploads",
            params={"file_length": len(image_bytes), "file_type": content_type},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if start_resp.status_code >= 400:
            raise MediaUploadError("start_upload_session", start_resp.text)
        upload_session_id = start_resp.json().get("id")
        if not upload_session_id:
            raise MediaUploadError("start_upload_session", "Meta returned no upload session id.")

        upload_resp = await client.post(
            f"{_base_url()}/{upload_session_id}",
            headers={"Authorization": f"OAuth {access_token}", "file_offset": "0"},
            content=image_bytes,
        )
        if upload_resp.status_code >= 400:
            raise MediaUploadError("upload_bytes", upload_resp.text)
        header_handle = upload_resp.json().get("h")
        if not header_handle:
            raise MediaUploadError("upload_bytes", "Meta returned no header handle.")

    return str(header_handle)
