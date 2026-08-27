import datetime
import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from customers.domain.models import Customer
from shared.db import Base


class MerchantAppointmentCounter(Base):
    """One row per merchant, tracking the next appointment_number to hand
    out -- same atomic-upsert pattern as orders/domain/models.py's
    MerchantOrderCounter (see appointments/adapters/repository.py's
    `_next_appointment_number`), and for the same reason: a per-merchant,
    gap-free sequence that's safe under concurrent inserts."""

    __tablename__ = "merchant_appointment_counters"

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("merchants.merchant_id"), primary_key=True
    )
    next_appointment_number: Mapped[int] = mapped_column(default=1)


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (UniqueConstraint("merchant_id", "appointment_number"),)

    appointment_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.customer_id"), index=True)

    # Human-facing sequential reference (per merchant, starts at 1, never
    # reused/reset) -- shown in the dashboard and WhatsApp messages instead
    # of the UUID primary key. See MerchantAppointmentCounter above for how
    # it's assigned.
    appointment_number: Mapped[int] = mapped_column()

    appointment_date: Mapped[datetime.date] = mapped_column()
    appointment_time: Mapped[datetime.time] = mapped_column()
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))

    # See appointments/domain/state_machine.py for the allowed values and
    # transitions -- Appointment is deliberately the only place that
    # mutates this, always through that module's transition_status.
    status: Mapped[str] = mapped_column(String(32), default="requested")

    whatsapp_conversation_ref: Mapped[str | None] = mapped_column(String(255), default=None)

    requested_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
    confirmed_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
    cancelled_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    # No back_populates on Customer -- nothing there needs the reverse
    # collection today, matching Order.customer's same choice.
    customer: Mapped["Customer"] = relationship()
