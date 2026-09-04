import datetime
import uuid

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
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


# Campaign.status -- no dedicated "cancelled" or "partially_sent" value.
# A merchant-cancel maps onto "failed" (distinguished only by which
# CampaignRecipient rows are "sent" vs "pending" at cancel time); a
# tier-capped campaign stays "sending" (not "completed") until every
# recipient row reaches a terminal status, even across a day boundary --
# see campaigns/domain/send_orchestrator.py's overflow-to-next-tick design.
CAMPAIGN_STATUSES = ("draft", "scheduled", "sending", "completed", "failed")

# CampaignRecipient.status -- this codebase's own design, not specified by
# Meta or the roadmap ticket. skipped_opted_out/skipped_no_number are
# terminal, not retried; a merchant re-targets by creating a fresh campaign
# (ARCHITECTURE.md Section 10's existing "no retry/backoff sophistication
# for outbound WhatsApp sends" rule, applied here too).
CAMPAIGN_RECIPIENT_STATUSES = (
    "pending",
    "sent",
    "failed",
    "skipped_opted_out",
    "skipped_no_number",
)


class Campaign(Base):
    __tablename__ = "campaigns"

    campaign_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("message_templates.template_id"))

    # {"kind": "all"} | {"kind": "ordered_within_days", "days": int} |
    # {"kind": "no_order_within_days", "days": int}, plus an unused
    # "segment_id" key -- an explicit extension point for the (separate,
    # not-yet-built) Customer Segmentation Engine roadmap ticket to
    # populate later without a migration. See campaigns/domain/audience.py.
    audience_filter: Mapped[dict[str, object]] = mapped_column(JSON)

    # None means "send on the very next scheduler tick" (send-now).
    scheduled_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(String(16), default="draft")

    # A StaffUser id (as a string) for a dashboard-created campaign, or a
    # "system:<job-name>" sentinel for one a future scheduled job (Automated
    # Reorder Reminders, Lost Customer Win-back) creates via create_campaign()
    # directly -- mirrors OrderStatusEvent.changed_by's existing
    # human-or-system string convention exactly.
    created_by: Mapped[str] = mapped_column(String(64))

    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(default=None)


class CampaignRecipient(Base):
    """Append-only per-recipient send ledger -- same shape as
    PaymentEvent/OrderStatusEvent: one row per (campaign, customer),
    materialized once when a campaign first starts sending, then updated
    in place as each recipient's send is attempted. This is what makes
    Campaign.status's five-value enum honest under tier-capping -- the
    campaign itself just stays "sending" while these rows track exactly
    who has and hasn't been reached yet."""

    __tablename__ = "campaign_recipients"
    __table_args__ = (UniqueConstraint("campaign_id", "customer_id"),)

    recipient_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.campaign_id"), index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.customer_id"), index=True)

    status: Mapped[str] = mapped_column(String(20), default="pending")
    sent_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
    failure_reason: Mapped[str | None] = mapped_column(Text, default=None)
    # Captured for future delivery-status reconciliation (sent/delivered/
    # read/failed callbacks) -- write-only today, since no delivery-status
    # webhook parsing exists yet (see docs/broadcast-implementation-plan.md's
    # Open Questions).
    whatsapp_message_id: Mapped[str | None] = mapped_column(String(255), default=None)
