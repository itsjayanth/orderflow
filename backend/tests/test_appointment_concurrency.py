"""Task 2: the highest-risk logic in the appointments feature -- two people
must never end up booked into the same slot. AppointmentRepository.create's
_assert_no_overlap uses pg_advisory_xact_lock(hashtext('appointments:{merchant}:{date}'))
to serialize concurrent booking attempts for the same (merchant, date) pair
(see that method's docstring in appointments/adapters/repository.py for why
a plain SELECT ... FOR UPDATE isn't enough on its own -- it can't lock rows
that don't exist yet, so two concurrent requests for a never-before-booked
slot would both pass an empty-result overlap check). This test proves that
lock actually does its job under real concurrency, not just when calls
happen to run sequentially in the same test."""

import asyncio
import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from appointments.adapters.repository import AppointmentRepository, SlotConflictError
from appointments.domain.models import Appointment
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from shared.db import SessionFactory
from shared.tenant import TenantContext

_FUTURE_DATE = datetime.date.today() + datetime.timedelta(days=30)


async def _make_tenant(db_session: AsyncSession) -> TenantContext:
    merchant = await MerchantRepository(db_session).create(
        business_name="Concurrency Test Business", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    await db_session.commit()
    return TenantContext(merchant_id=merchant.merchant_id)


async def _create_in_own_session(
    tenant: TenantContext, *, customer_whatsapp_number: str
) -> Appointment | SlotConflictError:
    """Each concurrent attempt gets its own session/transaction -- the real
    shape of two simultaneous HTTP requests, each with its own
    FastAPI-request-scoped session, not two operations sharing one
    session (which SQLAlchemy doesn't support concurrently anyway).
    Returns the exception instead of letting it propagate so
    asyncio.gather can collect both outcomes rather than short-circuiting
    on the first failure."""
    async with SessionFactory() as session:
        customer = await CustomerRepository(session).find_or_create(
            tenant, customer_whatsapp_number, display_name="Concurrent Customer"
        )
        try:
            appointment = await AppointmentRepository(session).create(
                tenant,
                customer_id=customer.customer_id,
                name="Concurrent Customer",
                email="concurrent@example.com",
                appointment_date=_FUTURE_DATE,
                start_time=datetime.time(15, 0),
                end_time=datetime.time(15, 30),
            )
            await session.commit()
            return appointment
        except SlotConflictError as exc:
            await session.rollback()
            return exc


async def test_two_concurrent_bookings_for_the_same_slot_exactly_one_succeeds(
    db_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(db_session)

    results = await asyncio.gather(
        _create_in_own_session(tenant, customer_whatsapp_number="+919876543210"),
        _create_in_own_session(tenant, customer_whatsapp_number="+919876543211"),
    )

    successes = [r for r in results if isinstance(r, Appointment)]
    conflicts = [r for r in results if isinstance(r, SlotConflictError)]
    assert len(successes) == 1, "exactly one of the two concurrent bookings must win"
    assert len(conflicts) == 1, "the loser must see SlotConflictError, not a silent double-booking"

    # No double row persisted -- the DB itself, not just the two calls'
    # return values, agrees only one booking exists for this slot.
    async with SessionFactory() as session:
        result = await session.execute(
            select(Appointment).where(
                Appointment.merchant_id == tenant.merchant_id,
                Appointment.appointment_date == _FUTURE_DATE,
                Appointment.start_time == datetime.time(15, 0),
                Appointment.status != "cancelled",
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1


async def test_two_concurrent_bookings_for_different_slots_both_succeed(
    db_session: AsyncSession,
) -> None:
    """Sanity check that the advisory lock only serializes, never rejects,
    concurrent attempts that don't actually conflict -- the lock key is
    scoped to (merchant, date), so both of these briefly contend on the
    same lock but neither sees the other's row in its overlap check."""
    tenant = await _make_tenant(db_session)

    async def _create_at(start_time: datetime.time, phone: str) -> Appointment | SlotConflictError:
        async with SessionFactory() as session:
            customer = await CustomerRepository(session).find_or_create(
                tenant, phone, display_name="Customer"
            )
            try:
                appointment = await AppointmentRepository(session).create(
                    tenant,
                    customer_id=customer.customer_id,
                    name="Customer",
                    email="customer@example.com",
                    appointment_date=_FUTURE_DATE,
                    start_time=start_time,
                    end_time=(
                        datetime.datetime.combine(_FUTURE_DATE, start_time)
                        + datetime.timedelta(minutes=30)
                    ).time(),
                )
                await session.commit()
                return appointment
            except SlotConflictError as exc:
                await session.rollback()
                return exc

    results = await asyncio.gather(
        _create_at(datetime.time(9, 0), "+919876543212"),
        _create_at(datetime.time(10, 0), "+919876543213"),
    )

    assert all(isinstance(r, Appointment) for r in results)
