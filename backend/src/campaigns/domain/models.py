import datetime
import uuid

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base

# Meta's fixed set for POST /{waba_id}/message_templates -- MARKETING is
# what broadcast campaigns actually send; UTILITY is included since a
# merchant may also want a Meta-approved template for a non-promotional
# use (e.g. a future non-order-lifecycle notification) without needing a
# second, parallel template system.
TEMPLATE_CATEGORIES = ("MARKETING", "UTILITY")

# NONE/TEXT/IMAGE only -- Phase 1 scope. VIDEO/DOCUMENT are a small
# additive change on top of the same header_media_handle mechanism (see
# campaigns/adapters/media_upload.py), sequenced into a later phase rather
# than built now.
TEMPLATE_HEADER_TYPES = ("NONE", "TEXT", "IMAGE")

# Meta's own lifecycle for a submitted template. "pending" is the only
# status this codebase ever sets directly (at submission); every other
# value only ever arrives via the message_template_status_update webhook
# (campaigns/domain/template_status.py), never polled for.
TEMPLATE_APPROVAL_STATUSES = ("pending", "approved", "rejected", "paused", "disabled")


class MessageTemplate(Base):
    """A merchant's WhatsApp template, submitted for real via
    POST /{waba_id}/message_templates using the access token Embedded
    Signup already obtained and verified (onboarding/domain/
    embedded_signup.py's _verify_waba_scope) -- not a placeholder for a
    template the merchant created by hand in Meta Business Manager.

    Deliberately a new model, not an extension of notifications/domain/
    models.py's NotificationTemplate: that model holds merchant-authored
    freeform {{var}} text rendered and sent locally, with no Meta template
    id, category, or approval concept at all. A MARKETING template needs
    real Meta submission and approval tracking NotificationTemplate was
    never built for."""

    __tablename__ = "message_templates"

    template_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)

    # Meta requires lowercase snake_case, unique per WABA+language --
    # normalized on save by template_validation.py, not enforced by a DB
    # constraint (Meta's own API is the source of truth for uniqueness;
    # a duplicate name surfaces as a 4xx from create_template()).
    name: Mapped[str] = mapped_column(String(512))
    category: Mapped[str] = mapped_column(String(16))
    language_code: Mapped[str] = mapped_column(String(16), default="en_US")

    header_type: Mapped[str] = mapped_column(String(16), default="NONE")
    header_text: Mapped[str | None] = mapped_column(String(60), default=None)
    # Meta's opaque Resumable-Upload handle, only set for an IMAGE (later,
    # VIDEO/DOCUMENT) header -- becomes the HEADER component's
    # example.header_handle at submission time.
    header_media_handle: Mapped[str | None] = mapped_column(String(512), default=None)

    body_text: Mapped[str] = mapped_column(Text)
    # Derived from body_text at save time (count of {{1}}, {{2}}, ...) so
    # later validation/rendering doesn't have to re-parse body_text.
    body_variable_count: Mapped[int] = mapped_column(default=0)
    footer_text: Mapped[str | None] = mapped_column(String(60), default=None)
    # list[{"type": "QUICK_REPLY" | "URL", "text": str, "url": str | None}]
    # -- the URL type mirrors conversation/adapters/whatsapp_client.py's
    # existing send_cta_url_button pattern, just submitted as part of a
    # template instead of sent ad hoc.
    buttons: Mapped[list[dict[str, str | None]]] = mapped_column(JSON, default=list)

    meta_template_id: Mapped[str | None] = mapped_column(String(255), default=None)
    meta_approval_status: Mapped[str] = mapped_column(String(16), default="pending")
    meta_rejection_reason: Mapped[str | None] = mapped_column(Text, default=None)

    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )
