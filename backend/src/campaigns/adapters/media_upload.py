from typing import Literal

import httpx

from onboarding.domain.models import WhatsAppBusinessAccount
from shared.config import get_settings
from shared.encryption import decrypt

MediaKind = Literal["image", "video", "document"]

# Per-kind caps/allowed MIME types, per Meta's documented template-header
# limits -- the only thing that changes between IMAGE (Phase 13) and
# VIDEO/DOCUMENT (Phase 16); the Resumable Upload call itself
# (upload_header_media's body) is identical for every kind, since Meta's
# upload API is media-type-agnostic at that layer.
_MAX_SIZE_BYTES: dict[MediaKind, int] = {
    "image": 5 * 1024 * 1024,
    "video": 16 * 1024 * 1024,
    "document": 100 * 1024 * 1024,
}
_ALLOWED_CONTENT_TYPES: dict[MediaKind, frozenset[str]] = {
    "image": frozenset({"image/jpeg", "image/png"}),
    "video": frozenset({"video/mp4", "video/3gpp"}),
    "document": frozenset({"application/pdf"}),
}


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


async def upload_header_media(
    kind: MediaKind, waba: WhatsAppBusinessAccount, data: bytes, content_type: str
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
    app-level credential.

    `kind` only selects the size/MIME check below (Phase 13 shipped this
    as upload_header_image, image-only; Phase 16 widened it to also cover
    video/document headers) -- the upload mechanics themselves don't
    branch on it at all."""
    if content_type not in _ALLOWED_CONTENT_TYPES[kind]:
        raise MediaUploadError(
            "precondition", f"Unsupported {kind} type {content_type!r} for a template header."
        )
    if len(data) > _MAX_SIZE_BYTES[kind]:
        raise MediaUploadError(
            "precondition",
            f"{kind.capitalize()} header must be at most {_MAX_SIZE_BYTES[kind]} bytes.",
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
            params={"file_length": len(data), "file_type": content_type},
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
            content=data,
        )
        if upload_resp.status_code >= 400:
            raise MediaUploadError("upload_bytes", upload_resp.text)
        header_handle = upload_resp.json().get("h")
        if not header_handle:
            raise MediaUploadError("upload_bytes", "Meta returned no header handle.")

    return str(header_handle)
