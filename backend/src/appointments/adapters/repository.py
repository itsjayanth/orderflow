import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from appointments.domain.models import Appointment, MerchantAppointmentCounter
from appointments.domain.state_machine import transition_status
from shared.tenant import TenantContext


class AppointmentNotFoundError(Exception):
    pass


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

    async def create(
        self,
        tenant: TenantContext,
        *,
        customer_id: uuid.UUID,
        name: str,
        email: str,
        appointment_date: datetime.date,
        appointment_time: datetime.time,
        notes: str | None = None,
        whatsapp_conversation_ref: str | None = None,
    ) -> Appointment:
        """Called by appointment_flow.domain.booking.perform_booking (the
        public booking webview) -- the only entry point that creates
        Appointment rows. status is set directly to "requested" here
        rather than routed through the domain state machine, matching
        OrderRepository.create's convention for the initial write of a
        state-machine-governed field."""
        appointment_number = await self._next_appointment_number(tenant.merchant_id)
        appointment = Appointment(
            merchant_id=tenant.merchant_id,
            customer_id=customer_id,
            appointment_number=appointment_number,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            notes=notes,
            name=name,
            email=email,
            status="requested",
            whatsapp_conversation_ref=whatsapp_conversation_ref,
        )
        self._session.add(appointment)
        await self._session.flush()
        return appointment

    async def get(self, tenant: TenantContext, appointment_id: uuid.UUID) -> Appointment | None:
        result = await self._session.execute(
            select(Appointment)
            .where(
                Appointment.appointment_id == appointment_id,
                Appointment.merchant_id == tenant.merchant_id,
            )
            .options(selectinload(Appointment.customer))
        )
        return result.scalar_one_or_none()

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
            .order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc())
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
        self, tenant: TenantContext, appointment_id: uuid.UUID, to_status: str
    ) -> Appointment:
        """The only path that mutates status -- always goes through the
        domain state machine first (defense in depth, same rationale as
        OrderRepository.transition_fulfillment_status)."""
        appointment = await self.get(tenant, appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(appointment_id)

        transition_status(appointment, to_status)
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
