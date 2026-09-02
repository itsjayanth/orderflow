import datetime
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
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


class AppointmentService(Base):
    """A bookable service type (e.g. "Haircut", "Consultation"), scoped per
    merchant. Optional: a merchant with zero rows here just has a single
    generic, undifferentiated appointment type -- the public booking flow
    skips the service-select step entirely when this list is empty (see
    appointment_flow/api/router.py's services endpoint)."""

    __tablename__ = "appointment_services"

    service_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    duration_minutes: Mapped[int] = mapped_column()
    # Deposit/service price for the payment placeholder (Task 5) -- nullable
    # since not every merchant charges per-service.
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)


class StaffResource(Base):
    """A schedulable staff member/resource -- deliberately separate from
    identity.domain.models.StaffUser, which is a dashboard *login account*
    (email/password/role). A business can have staff who never log into
    the dashboard, or a dashboard user who never personally takes
    appointments, so these two concepts must not be conflated. Unused by
    any UI yet (multi-staff scheduling is a later phase) -- exists now so
    Appointment.staff_id has somewhere to point without a future breaking
    migration."""

    __tablename__ = "staff_resources"

    staff_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)


class MerchantAvailability(Base):
    """One row per (merchant, day_of_week[, staff]) working-hours window.
    appointment_flow/domain/availability.py's get_available_slots() slices
    this into slot_duration_minutes increments and subtracts already-booked
    ranges (padded by buffer_minutes) to compute open slots. No row for a
    given day means the merchant hasn't configured hours for that day --
    get_available_slots() returns an empty list rather than guessing at
    default hours, matching this codebase's "safe default over guessing"
    convention (see Merchant.vertical -- the appointment vertical's own
    gate for whether this feature applies to a merchant at all)."""

    __tablename__ = "merchant_availability"

    availability_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.merchant_id"), index=True)
    # NULL = applies merchant-wide (the only case any UI writes today).
    # Per-staff override rows are schema-ready but unused until multi-staff
    # scheduling ships.
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff_resources.staff_id"), default=None
    )
    # Python's date.weekday(): 0=Monday .. 6=Sunday.
    day_of_week: Mapped[int] = mapped_column()
    start_time: Mapped[datetime.time] = mapped_column()
    end_time: Mapped[datetime.time] = mapped_column()
    slot_duration_minutes: Mapped[int] = mapped_column(default=30)
    buffer_minutes: Mapped[int] = mapped_column(default=0)


class AppointmentReminder(Base):
    """Idempotency record for the reminder scan
    (shared/scheduler.py's send_due_appointment_reminders) -- a row exists
    if and only if that (appointment, offset_hours) reminder was actually
    sent successfully. The scan computes what's "due" fresh every 5
    minutes rather than pre-queuing anything (see the plan's Task 4), so
    this table's only job is "don't send the same reminder twice": a row
    is inserted only after `send_template_message` returns True, never
    when a reminder merely becomes eligible, so a failed send is naturally
    retried on the next scan rather than permanently marked done. That
    "only insert on success" invariant is why sent_at is NOT NULL with no
    separate "pending" state, unlike the nullable sent_at the plan
    sketched -- existence of the row already means "sent"."""

    __tablename__ = "appointment_reminders"
    __table_args__ = (UniqueConstraint("appointment_id", "offset_hours"),)

    reminder_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("appointments.appointment_id"), index=True
    )
    offset_hours: Mapped[int] = mapped_column()
    sent_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )


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
    # Renamed from appointment_time -- end_time (added alongside) makes
    # this genuinely a range now, not a single instant, so "start_time"
    # reads correctly next to it. See appointments/adapters/repository.py's
    # overlap-check query for why both are needed as real columns rather
    # than start_time + a derived duration.
    start_time: Mapped[datetime.time] = mapped_column()
    end_time: Mapped[datetime.time] = mapped_column()

    service_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("appointment_services.service_id"), default=None
    )
    # Unused by any UI yet -- see StaffResource's docstring.
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff_resources.staff_id"), default=None
    )

    notes: Mapped[str | None] = mapped_column(Text, default=None)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))

    # See appointments/domain/state_machine.py for the allowed values and
    # transitions -- Appointment is deliberately the only place that
    # mutates this, always through that module's transition_status.
    status: Mapped[str] = mapped_column(String(32), default="requested")

    # 'flow' | 'browser' | 'dashboard' -- which surface created this row,
    # for reporting/debugging (e.g. "did the BROWSER_LINK rollout actually
    # shift booking volume"). Not enforced against a DB check constraint;
    # every write path sets it explicitly (perform_booking, the dashboard's
    # future manual-booking path).
    created_via: Mapped[str] = mapped_column(String(16), default="browser")

    # 'not_required' | 'pending' | 'paid' | 'failed' -- Task 5 placeholder,
    # mirrors Order.payment_status's shape. 'not_required' is the default
    # since most appointment bookings don't need a deposit.
    payment_status: Mapped[str] = mapped_column(String(16), default="not_required")

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
