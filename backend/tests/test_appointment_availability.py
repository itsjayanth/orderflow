import datetime
import uuid
import zoneinfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from appointment_flow.domain.availability import get_available_slots, is_slot_elapsed
from appointment_flow.domain.booking import PastDateError, perform_booking
from appointments.adapters.repository import SlotConflictError
from appointments.adapters.scheduling_repository import MerchantAvailabilityRepository
from identity.adapters.repository import MerchantRepository
from identity.domain.models import Merchant
from shared.tenant import TenantContext

_TZ = "Asia/Kolkata"  # UTC+5:30


async def _make_tenant(db_session: AsyncSession) -> tuple[Merchant, TenantContext]:
    merchant = await MerchantRepository(db_session).create(
        business_name="Slot Test Business", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    merchant.appointment_enabled = True
    merchant.timezone = _TZ
    await db_session.commit()
    return merchant, TenantContext(merchant_id=merchant.merchant_id)


async def _set_hours(
    db_session: AsyncSession,
    tenant: TenantContext,
    *,
    day_of_week: int,
    start: datetime.time = datetime.time(9, 0),
    end: datetime.time = datetime.time(18, 0),
    slot_duration_minutes: int = 30,
) -> None:
    await MerchantAvailabilityRepository(db_session).replace_all(
        tenant,
        windows=[
            {
                "day_of_week": day_of_week,
                "start_time": start,
                "end_time": end,
                "slot_duration_minutes": slot_duration_minutes,
                "buffer_minutes": 0,
            }
        ],
    )
    await db_session.commit()


# --- Task 1: get_available_slots excludes elapsed slots -------------------


async def test_elapsed_slots_excluded_for_today(db_session: AsyncSession) -> None:
    merchant, tenant = await _make_tenant(db_session)
    # A fixed local "today" (mocked "now" is 13:15 IST) rather than the
    # real wall-clock date, so this test's assertions never depend on when
    # it happens to run.
    today = datetime.date(2026, 9, 3)
    await _set_hours(db_session, tenant, day_of_week=today.weekday())

    # "Now" is 13:15 local time -- every slot starting at/before 13:00
    # must be gone, everything from 13:30 onward must remain.
    now_utc = datetime.datetime.combine(
        today, datetime.time(13, 15), tzinfo=zoneinfo.ZoneInfo(_TZ)
    ).astimezone(datetime.UTC)

    slots = await get_available_slots(
        db_session,
        tenant,
        appointment_date=today,
        service_duration_minutes=30,
        timezone=_TZ,
        now_utc=now_utc,
    )

    assert all(slot.start_time > datetime.time(13, 15) for slot in slots)
    assert datetime.time(13, 30) in {slot.start_time for slot in slots}
    assert datetime.time(9, 0) not in {slot.start_time for slot in slots}
    assert datetime.time(13, 0) not in {slot.start_time for slot in slots}


async def test_future_date_unaffected_by_elapsed_time_filter(db_session: AsyncSession) -> None:
    merchant, tenant = await _make_tenant(db_session)
    future_date = datetime.date.today() + datetime.timedelta(days=10)
    await _set_hours(db_session, tenant, day_of_week=future_date.weekday())

    slots = await get_available_slots(
        db_session,
        tenant,
        appointment_date=future_date,
        service_duration_minutes=30,
        timezone=_TZ,
    )

    # Full 9:00-18:00 window at 30-minute cadence = 18 slots, none dropped
    # for a date that's nowhere near "now".
    assert len(slots) == 18
    assert datetime.time(9, 0) in {slot.start_time for slot in slots}


# --- is_slot_elapsed -------------------------------------------------------


def test_is_slot_elapsed_true_for_a_past_time_today() -> None:
    now_utc = datetime.datetime(2026, 9, 3, 10, 0, tzinfo=datetime.UTC)  # 15:30 IST
    assert is_slot_elapsed(
        appointment_date=datetime.date(2026, 9, 3),
        start_time=datetime.time(15, 0),
        timezone=_TZ,
        now_utc=now_utc,
    )


def test_is_slot_elapsed_false_for_a_future_time_today() -> None:
    now_utc = datetime.datetime(2026, 9, 3, 10, 0, tzinfo=datetime.UTC)  # 15:30 IST
    assert not is_slot_elapsed(
        appointment_date=datetime.date(2026, 9, 3),
        start_time=datetime.time(16, 0),
        timezone=_TZ,
        now_utc=now_utc,
    )


# --- Task 3: perform_booking re-validates live, not from a stale slot -----


async def test_perform_booking_rejects_elapsed_same_day_slot(db_session: AsyncSession) -> None:
    merchant, tenant = await _make_tenant(db_session)

    with pytest.raises(PastDateError):
        await perform_booking(
            db_session,
            tenant,
            merchant,
            customer_whatsapp_number="+919876543210",
            customer_display_name="Asha",
            name="Asha Rao",
            email="asha@example.com",
            appointment_date=datetime.date.today(),
            # Midnight has already elapsed by the time any test runs.
            start_time=datetime.time(0, 0),
        )


async def test_perform_booking_rejects_slot_outside_current_hours(
    db_session: AsyncSession,
) -> None:
    merchant, tenant = await _make_tenant(db_session)
    future_date = datetime.date.today() + datetime.timedelta(days=10)
    await _set_hours(
        db_session,
        tenant,
        day_of_week=future_date.weekday(),
        start=datetime.time(9, 0),
        end=datetime.time(12, 0),
    )

    with pytest.raises(SlotConflictError):
        await perform_booking(
            db_session,
            tenant,
            merchant,
            customer_whatsapp_number="+919876543210",
            customer_display_name="Asha",
            name="Asha Rao",
            email="asha@example.com",
            appointment_date=future_date,
            # Outside the 09:00-12:00 window the merchant just configured.
            start_time=datetime.time(14, 0),
        )


async def test_perform_booking_permissive_when_no_hours_configured(
    db_session: AsyncSession,
) -> None:
    """No MerchantAvailability row at all -- still bookable, matching
    resolve_duration_minutes's own documented fallback. Only a merchant
    who has actually configured hours gets the live re-validation."""
    merchant, tenant = await _make_tenant(db_session)
    future_date = datetime.date.today() + datetime.timedelta(days=10)

    result = await perform_booking(
        db_session,
        tenant,
        merchant,
        customer_whatsapp_number="+919876543210",
        customer_display_name="Asha",
        name="Asha Rao",
        email="asha@example.com",
        appointment_date=future_date,
        start_time=datetime.time(23, 0),
    )

    assert result.appointment.status == "requested"
