import datetime
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class MerchantPaymentCredentials(Base):
    """1:1 with Merchant. `razorpay_key_id` is stored in the clear (it's
    not secret -- it's sent to the browser/customer in real Razorpay
    Checkout flows); `razorpay_key_secret_encrypted` never leaves the
    backend unencrypted."""

    __tablename__ = "merchant_payment_credentials"

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("merchants.merchant_id"), primary_key=True
    )
    razorpay_key_id: Mapped[str | None] = mapped_column(String(255), default=None)
    razorpay_key_secret_encrypted: Mapped[str | None] = mapped_column(String(2048), default=None)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )


class PaymentEvent(Base):
    """Append-only -- the source of truth for payment state. Order.payment_status
    is a derived/materialized view over this, per ARCHITECTURE.md Section 1.
    Appointment.payment_status (placeholder payment-link work) is the same
    pattern -- one shared table/repository, entity type inferred from
    which of order_id/appointment_id is set, rather than a parallel
    AppointmentPaymentEvent table duplicating this whole class."""

    __tablename__ = "payment_events"
    __table_args__ = (
        CheckConstraint(
            "(order_id IS NOT NULL) != (appointment_id IS NOT NULL)",
            name="ck_payment_events_exactly_one_entity",
        ),
    )

    payment_event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.order_id"), index=True, default=None
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("appointments.appointment_id"), index=True, default=None
    )

    provider: Mapped[str] = mapped_column(String(32))  # "razorpay" | "dummy" | "cod"
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), default=None, index=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(255), default=None)

    # link_created, payment_succeeded, payment_failed,
    # webhook_received_duplicate, cod_selected, cod_collected
    event_type: Mapped[str] = mapped_column(String(64))
    raw_payload: Mapped[str | None] = mapped_column(Text, default=None)
    # "system" for webhook-driven events, a staff_user_id for cod_collected.
    recorded_by: Mapped[str] = mapped_column(String(64), default="system")

    received_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
