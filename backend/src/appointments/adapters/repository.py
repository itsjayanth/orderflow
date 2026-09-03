import datetime
import uuid

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from appointments.domain.models import (
    Appointment,
    AppointmentStatusEvent,
    MerchantAppointmentCounter,
)
from appointments.domain.state_machine import transition_status
from shared.tenant import TenantContext


class AppointmentNotFoundError(Exception):
    pass


class SlotConflictError(Exception):
    """Raised when the requested [start_time, end_time) range overlaps an
    existing non-cancelled appointment for the same merchant (and staff,
    once staff assignment is in use). The API layer turns this into a 409
    with a machine-readable reason so the frontend can refresh available
    slots rather than show a generic error."""


class AppointmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _next_appointment_number(self, merchant_id: uuid.UUID) -> int:
        """Atomically hands out the next per-merchant appointment_number --
        see orders/adapters/repository.py's `_next_order_number` for the
        exact same pattern and why it's safe under concurrent creation."""
        stmt = (
            pg_insert(MerchantAppointmentCounter)
            .values(merchant_id=merchant_id, next_appointment_number=2)
            .on_conflict_do_update(
                index_elements=[MerchantAppointmentCounter.merchant_id],
                set_={
                    "next_appointment_number": (
                        MerchantAppointmentCounter.__table__.c.next_appointment_number + 1
                    )
                },
            )
            .returning(MerchantAppointmentCounter.next_appointment_number)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() - 1

    async def _assert_no_overlap(
        self,
        merchant_id: uuid.UUID,
        *,
        appointment_date: datetime.date,
        start_time: datetime.time,
        end_time: datetime.time,
        staff_id: uuid.UUID | None,
        exclude_appointment_id: uuid.UUID | None = None,
    ) -> None:
        """Race-condition-safe overlap check -- must run inside the same
        transaction as the INSERT/UPDATE that follows it.

        A plain `SELECT ... FOR UPDATE` is NOT sufficient on its own here:
        FOR UPDATE only locks rows the SELECT actually reads, and a slot
        nobody has booked yet has zero existing rows to lock -- two
        concurrent requests for the very same never-before-booked slot
        would each see an empty result set and both proceed to INSERT,
        which is exactly the double-booking this exists to prevent
        (a classic phantom-read gap, not covered by Postgres's default READ
        COMMITTED isolation). `pg_advisory_xact_lock` closes that gap: it
        serializes every booking/reschedule attempt for the same
        (merchant, date) pair -- transaction-scoped, auto-released on
        commit or rollback -- so a second concurrent transaction blocks
        here until the first one finishes, and then its own SELECT
        correctly sees whatever the first one just committed.

        staff_id scoping: no UI sets staff_id yet, so every appointment for
        a merchant is created with staff_id=NULL today. Two NULL-staff
        appointments must still be detected as competing for the same
        capacity -- `staff_id IS NOT DISTINCT FROM :staff_id` treats NULL
        as an ordinary equal-to-NULL value (unlike `=`, which is never true
        for NULL), so this naturally degrades to "one shared calendar per
        merchant" today and becomes real per-staff isolation the moment a
        booking path starts passing a real staff_id. The advisory lock key
        is scoped to (merchant_id, date) only, not staff_id -- coarser than
        it needs to be once multi-staff ships (it'll serialize different
        staff members' bookings on the same day against each other
        unnecessarily), but correct, and cheap to narrow later."""
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"appointments:{merchant_id}:{appointment_date.isoformat()}"},
        )

        # asyncpg's prepared-statement type inference can't resolve a
        # parameter's type when it only ever appears in an `IS NULL`/`!=`
        # comparison with no other type context (AmbiguousParameterError)
        # -- explicit ::uuid/::time casts sidestep that, harmlessly, since
        # every value here already comes in as the right Python type.
        stmt = text(
            """
            SELECT 1 FROM appointments
            WHERE merchant_id = :merchant_id
              AND appointment_date = :appointment_date
              AND staff_id IS NOT DISTINCT FROM CAST(:staff_id AS uuid)
              AND status != 'cancelled'
              AND start_time < CAST(:end_time AS time)
              AND end_time > CAST(:start_time AS time)
              AND (
                CAST(:exclude_id AS uuid) IS NULL
                OR appointment_id != CAST(:exclude_id AS uuid)
              )
            """
        )
        result = await self._session.execute(
            stmt,
            {
                "merchant_id": merchant_id,
                "appointment_date": appointment_date,
                "staff_id": staff_id,
                "start_time": start_time,
                "end_time": end_time,
                "exclude_id": exclude_appointment_id,
            },
        )
        if result.first() is not None:
            raise SlotConflictError(
                f"slot {appointment_date} {start_time}-{end_time} already booked"
            )

    async def create(
        self,
        tenant: TenantContext,
        *,
        customer_id: uuid.UUID,
        name: str,
        email: str,
        appointment_date: datetime.date,
        start_time: datetime.time,
        end_time: datetime.time,
        service_id: uuid.UUID | None = None,
        staff_id: uuid.UUID | None = None,
        created_via: str = "browser",
        notes: str | None = None,
        whatsapp_conversation_ref: str | None = None,
    ) -> Appointment:
        """Called by appointment_flow.domain.booking.perform_booking (the
        public booking webview and the WhatsApp Flow completion handler) --
        the only entry point that creates Appointment rows. status is set
        directly to "requested" here rather than routed through the domain
        state machine, matching OrderRepository.create's convention for the
        initial write of a state-machine-governed field.

        Raises SlotConflictError if [start_time, end_time) overlaps an
        existing booking -- caller must be inside a transaction that will
        roll back on that exception (FastAPI's session-per-request +
        session.commit()-on-success pattern already used everywhere else in
        this codebase satisfies this automatically)."""
        await self._assert_no_overlap(
            tenant.merchant_id,
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            staff_id=staff_id,
        )

        appointment_number = await self._next_appointment_number(tenant.merchant_id)
        appointment = Appointment(
            merchant_id=tenant.merchant_id,
            customer_id=customer_id,
            appointment_number=appointment_number,
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            service_id=service_id,
            staff_id=staff_id,
            created_via=created_via,
            notes=notes,
            name=name,
            email=email,
            status="requested",
            whatsapp_conversation_ref=whatsapp_conversation_ref,
        )
        self._session.add(appointment)
        # Flushed alone first -- appointment_id is a column-level Python
        # default (uuid.uuid4), which SQLAlchemy only actually assigns to
        # the ORM instance once this INSERT is emitted, not at
        # Appointment(...) construction time. The event row below needs
        # the real id, so it can't be added in the same batch.
        await self._session.flush()
        self._session.add(
            AppointmentStatusEvent(
                appointment_id=appointment.appointment_id,
                event_type="requested",
                to_status="requested",
                to_appointment_date=appointment_date,
                to_start_time=start_time,
                # The initial request has no staff actor -- which surface
                # (flow/browser) created it is the closest thing to a
                # "who", see AppointmentStatusEvent's docstring.
                changed_by=created_via,
            )
        )
        await self._session.flush()
        return appointment

    async def get(self, tenant: TenantContext, appointment_id: uuid.UUID) -> Appointment | None:
        result = await self._session.execute(
            select(Appointment)
            .where(
                Appointment.appointment_id == appointment_id,
                Appointment.merchant_id == tenant.merchant_id,
            )
            .options(selectinload(Appointment.customer), selectinload(Appointment.status_events))
        )
        return result.scalar_one_or_none()

    async def list_booked_ranges(
        self,
        tenant: TenantContext,
        *,
        appointment_date: datetime.date,
        staff_id: uuid.UUID | None = None,
    ) -> list[tuple[datetime.time, datetime.time]]:
        """Every non-cancelled [start_time, end_time) range booked for this
        merchant/date -- used by appointment_flow.domain.availability's
        get_available_slots() to subtract from the working-hours window.
        Deliberately not staff-scoped by default (staff_id=None returns
        every booking regardless of staff_id, since no booking path sets
        staff_id yet and a merchant-wide calendar means every booking
        blocks every slot) -- pass staff_id explicitly once per-staff
        availability is real.

        NOTE: defined before list() below on purpose -- a method literally
        named `list` in this class shadows the builtin `list` for every
        annotation textually after it in the class body (class bodies
        resolve bare names against their own already-populated namespace
        first), so any later method using a bare `list[...]` return
        annotation would break at class-definition time. Keep any new
        method with a `list[...]`/`tuple[...]` annotation above the `list`
        method, not below it."""
        stmt = select(Appointment.start_time, Appointment.end_time).where(
            Appointment.merchant_id == tenant.merchant_id,
            Appointment.appointment_date == appointment_date,
            Appointment.status != "cancelled",
        )
        if staff_id is not None:
            stmt = stmt.where(Appointment.staff_id == staff_id)
        result = await self._session.execute(stmt)
        return [(row.start_time, row.end_time) for row in result.all()]

    async def list(
        self,
        tenant: TenantContext,
        status: str | None = None,
        from_date: datetime.date | None = None,
        to_date: datetime.date | None = None,
        customer_id: uuid.UUID | None = None,
    ) -> list[Appointment]:
        """Ordered soonest-first (ascending date/time) -- unlike orders,
        which list newest-placed-first, appointments are forward-looking:
        staff care about what's coming up next, not what was just booked."""
        stmt = (
            select(Appointment)
            .where(Appointment.merchant_id == tenant.merchant_id)
            .options(selectinload(Appointment.customer))
            .order_by(Appointment.appointment_date.asc(), Appointment.start_time.asc())
        )
        if status is not None:
            stmt = stmt.where(Appointment.status == status)
        if customer_id is not None:
            stmt = stmt.where(Appointment.customer_id == customer_id)
        if from_date is not None:
            stmt = stmt.where(Appointment.appointment_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(Appointment.appointment_date <= to_date)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def transition_status(
        self, tenant: TenantContext, appointment_id: uuid.UUID, to_status: str, *, changed_by: str
    ) -> Appointment:
        """The only path that mutates status -- always goes through the
        domain state machine first (defense in depth, same rationale as
        OrderRepository.transition_fulfillment_status). `changed_by` is
        the acting staff_user_id (str) -- see AppointmentStatusEvent's
        docstring for why every call today is staff-initiated."""
        appointment = await self.get(tenant, appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)

        from_status = appointment.status
        transition_status(appointment, to_status)

        self._session.add(
            AppointmentStatusEvent(
                appointment_id=appointment.appointment_id,
                event_type=to_status,
                from_status=from_status,
                to_status=to_status,
                changed_by=changed_by,
            )
        )
        await self._session.flush()
        return appointment

    async def update_notes(
        self, tenant: TenantContext, appointment_id: uuid.UUID, *, notes: str | None
    ) -> Appointment | None:
        """Dashboard notes edit. Only touches notes when explicitly passed
        (exclude_unset on the request schema) -- mirrors
        OrderRepository.update_details's same `is not None` guard, so
        notes can't be explicitly cleared to null through this path."""
        appointment = await self.get(tenant, appointment_id)
        if appointment is None:
            return None

        if notes is not None:
            appointment.notes = notes

        await self._session.flush()
        return appointment

    async def reschedule(
        self,
        tenant: TenantContext,
        appointment_id: uuid.UUID,
        *,
        appointment_date: datetime.date,
        start_time: datetime.time,
        end_time: datetime.time,
        changed_by: str,
    ) -> Appointment | None:
        """Dashboard-initiated date/time change. Deliberately NOT a
        appointments.domain.state_machine transition -- rescheduling
        doesn't change `status`, it's a plain field mutation, same
        rationale as update_notes above, just with the same
        overlap-safety guarantee create() gives a fresh booking (excluding
        this appointment's own current row from the conflict check, so it
        doesn't collide with itself). Records an AppointmentStatusEvent
        with both the old and new slot (Task 5) -- the original
        "requested" event's own slot fields are left untouched, so a
        reschedule is visible in the timeline rather than silently
        overwriting history."""
        appointment = await self.get(tenant, appointment_id)
        if appointment is None:
            return None

        await self._assert_no_overlap(
            tenant.merchant_id,
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            staff_id=appointment.staff_id,
            exclude_appointment_id=appointment_id,
        )

        from_appointment_date = appointment.appointment_date
        from_start_time = appointment.start_time
        appointment.appointment_date = appointment_date
        appointment.start_time = start_time
        appointment.end_time = end_time

        self._session.add(
            AppointmentStatusEvent(
                appointment_id=appointment.appointment_id,
                event_type="rescheduled",
                from_appointment_date=from_appointment_date,
                from_start_time=from_start_time,
                to_appointment_date=appointment_date,
                to_start_time=start_time,
                changed_by=changed_by,
            )
        )
        await self._session.flush()
        return appointment
