import datetime
import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base

# The three notification kinds Phase 7 sends (orders/domain/events.py's
# OrderPaid/OrderConfirmedCOD both map to "order_confirmed").
NOTIFICATION_KINDS = ("order_confirmed", "order_ready", "order_completed")

# What actually goes out when a merchant hasn't configured (or has
# deactivated) their own template for a kind -- the Phase 7 behavior,
# unchanged. Single source of truth shared by the sending channel
# (notifications/adapters/whatsapp_channel.py) and the templates API
# (notifications/api/router.py, which shows these as the starting point for
# a merchant editing a template for the first time).
DEFAULT_MESSAGES: dict[str, str] = {
    "order_confirmed": "Order confirmed! We'll let you know when it's ready.",
    "order_ready": "Your order is ready!",
    "order_completed": "Your order is complete. Enjoy your meal!",
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

    # "order_confirmed" | "order_ready" | "order_completed"
    notification_kind: Mapped[str] = mapped_column(String(32))
    template_name: Mapped[str] = mapped_column(String(255))
    language_code: Mapped[str] = mapped_column(String(16), default="en")
    body: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)

    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )
