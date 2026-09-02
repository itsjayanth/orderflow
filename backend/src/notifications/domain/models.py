import datetime
import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base

# The four notification kinds sent over an order's lifecycle
# (orders/domain/events.py's OrderPaid/OrderConfirmedCOD both map to
# "order_confirmed"; "order_processing" fires on the new -> processing
# fulfillment transition), plus the three sent over an appointment's
# lifecycle (appointments/domain/events.py's AppointmentRequested/
# AppointmentConfirmed/AppointmentCancelled -- "completed" stays silent
# by product spec).
NOTIFICATION_KINDS = (
    "order_confirmed",
    "order_processing",
    "order_ready",
    "order_completed",
    "appointment_requested",
    "appointment_confirmed",
    "appointment_cancelled",
)

# What actually goes out when a merchant hasn't configured (or has
# deactivated) their own template for a kind -- the Phase 7 behavior,
# unchanged. Single source of truth shared by the sending channel
# (notifications/adapters/whatsapp_channel.py) and the templates API
# (notifications/api/router.py, which shows these as the starting point for
# a merchant editing a template for the first time). WhatsApp text messages
# support basic markdown (*bold*, _italic_), used here for a more polished
# look than a bare sentence.
DEFAULT_MESSAGES: dict[str, str] = {
    "order_confirmed": "✅ *Order #{{order_number}} confirmed!*\n\n{{items}}\n\n"
    "Total: {{currency}} {{total}}\n\n_We'll let you know when it's ready._",
    "order_processing": "🔄 *Order #{{order_number}} is being processed!*\n\n{{items}}\n\n"
    "_We'll notify you the moment it's ready._",
    "order_ready": "🎉 *Order #{{order_number}} is ready!*\n\nIt's on its way — you should be "
    "expecting it soon! 🛵",
    "order_completed": "✅ *Order #{{order_number}} complete!*\n\nThanks for ordering from "
    "{{business_name}} — enjoy your meal! 🍽️",
    "appointment_requested": "📝 *Appointment request received!*\n\n{{service_line}}📅 "
    "{{appointment_date}} at {{appointment_time}}\n\n_We'll message you here once it's confirmed._",
    "appointment_confirmed": "✅ *Your appointment is confirmed!*\n\n📅 {{appointment_date}} at "
    "{{appointment_time}}\n\n_See you then!_",
    "appointment_cancelled": "❌ *Your appointment on {{appointment_date}} at "
    "{{appointment_time}} has been cancelled.*\n\n_Contact us if you'd like to rebook._",
}


class NotificationTemplate(Base):
    """A merchant's own copy of an approved WhatsApp message template, per
    notification kind. Storing the literal template body (with `{{var}}`
    placeholders) rather than a Meta template ID/handle, since there's no
    live Meta Business account to fetch approved templates from -- a
    merchant fills this in themselves, matching whatever they've had
    approved on the Meta side. If no row exists (or `is_active` is false)
    for a kind, the channel falls back to the built-in plain-text message
    (notifications/adapters/whatsapp_channel.py's _DEFAULT_* constants)."""

    __tablename__ = "notification_templates"
    __table_args__ = (UniqueConstraint("merchant_id", "notification_kind"),)

    template_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)

    # One of NOTIFICATION_KINDS above.
    notification_kind: Mapped[str] = mapped_column(String(32))
    template_name: Mapped[str] = mapped_column(String(255))
    language_code: Mapped[str] = mapped_column(String(16), default="en")
    body: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)

    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )
