import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from appointments.domain.models import Appointment, AppointmentReminder
from shared.tenant import TenantContext


class AppointmentReminderRepository:
    """Backs the reminder scan (shared/scheduler.py's
    send_due_appointment_reminders) -- separate from AppointmentRepository
    the same way MerchantAvailabilityRepository/AppointmentServiceRepository
    got their own file (appointments/adapters/scheduling_repository.py):
    a distinct concern, not a distinct table's CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_confirmed_upcoming(
        self, tenant: TenantContext, *, on_or_after: datetime.date
    ) -> list[Appointment]:
        """Confirmed appointments from `on_or_after` (the merchant's own
        local "today", passed in by the caller) onward -- the reminder
        scan's candidate pool before per-offset due-checking. Bounded so
        this doesn't grow into scanning years of past completed/cancelled
        history; `status == "confirmed"` alone already excludes cancelled
        appointments, so a cancellation after a reminder was found "due"
        but before it's sent is naturally safe -- the next scan simply
        won't see that appointment here anymore."""
        result = await self._session.execute(
            select(Appointment)
            .where(
                Appointment.merchant_id == tenant.merchant_id,
                Appointment.status == "confirmed",
                Appointment.appointment_date >= on_or_after,
            )
            .options(selectinload(Appointment.customer))
        )
        return list(result.scalars().all())

    async def sent_offsets(self, appointment_id: uuid.UUID) -> set[int]:
        result = await self._session.execute(
            select(AppointmentReminder.offset_hours).where(
                AppointmentReminder.appointment_id == appointment_id
            )
        )
        return {row[0] for row in result.all()}

    async def mark_sent(self, appointment_id: uuid.UUID, offset_hours: int) -> None:
        self._session.add(
            AppointmentReminder(appointment_id=appointment_id, offset_hours=offset_hours)
        )
        await self._session.flush()
