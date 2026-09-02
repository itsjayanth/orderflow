import uuid
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from appointments.domain.models import AppointmentService, MerchantAvailability
from shared.tenant import TenantContext

# NOTE on method ordering in both classes below: a method literally named
# `list` shadows the builtin `list` for every annotation textually after it
# in the same class body (class bodies resolve bare names against their own
# already-populated namespace first, and annotations are evaluated eagerly
# at `def` time) -- so `list` is defined LAST in each class here, after
# every other method that uses a bare `list[...]`/`dict[...]` annotation.


class AppointmentServiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, tenant: TenantContext, service_id: uuid.UUID) -> AppointmentService | None:
        result = await self._session.execute(
            select(AppointmentService).where(
                AppointmentService.service_id == service_id,
                AppointmentService.merchant_id == tenant.merchant_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        tenant: TenantContext,
        *,
        name: str,
        duration_minutes: int,
        price: Decimal | None = None,
    ) -> AppointmentService:
        service = AppointmentService(
            merchant_id=tenant.merchant_id,
            name=name,
            duration_minutes=duration_minutes,
            price=price,
        )
        self._session.add(service)
        await self._session.flush()
        return service

    async def update(
        self,
        tenant: TenantContext,
        service_id: uuid.UUID,
        *,
        name: str | None = None,
        duration_minutes: int | None = None,
        price: Decimal | None = None,
        is_active: bool | None = None,
    ) -> AppointmentService | None:
        service = await self.get(tenant, service_id)
        if service is None:
            return None
        if name is not None:
            service.name = name
        if duration_minutes is not None:
            service.duration_minutes = duration_minutes
        if price is not None:
            service.price = price
        if is_active is not None:
            service.is_active = is_active
        await self._session.flush()
        return service

    async def delete(self, tenant: TenantContext, service_id: uuid.UUID) -> bool:
        service = await self.get(tenant, service_id)
        if service is None:
            return False
        await self._session.delete(service)
        await self._session.flush()
        return True

    async def list(
        self, tenant: TenantContext, *, include_inactive: bool = False
    ) -> list[AppointmentService]:
        stmt = select(AppointmentService).where(
            AppointmentService.merchant_id == tenant.merchant_id
        )
        if not include_inactive:
            stmt = stmt.where(AppointmentService.is_active.is_(True))
        result = await self._session.execute(stmt.order_by(AppointmentService.name.asc()))
        return list(result.scalars().all())


class MerchantAvailabilityRepository:
    """Merchant-wide availability only (staff_id always NULL through this
    repository) -- per-staff override rows are schema-ready on
    MerchantAvailability but no write path here creates them yet, matching
    StaffResource's "unused until multi-staff ships" status."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_all(
        self,
        tenant: TenantContext,
        *,
        windows: list[dict[str, object]],
    ) -> list[MerchantAvailability]:
        """Full replace, not per-day upsert -- the dashboard settings form
        always submits the complete weekly schedule at once (a day simply
        missing from `windows` means "closed that day"), so delete-then-
        recreate is simpler and race-free (no orphaned rows from a day
        that got removed) than diffing against what's already there."""
        await self._session.execute(
            delete(MerchantAvailability).where(
                MerchantAvailability.merchant_id == tenant.merchant_id,
                MerchantAvailability.staff_id.is_(None),
            )
        )
        rows = [
            MerchantAvailability(
                merchant_id=tenant.merchant_id,
                staff_id=None,
                day_of_week=w["day_of_week"],
                start_time=w["start_time"],
                end_time=w["end_time"],
                slot_duration_minutes=w.get("slot_duration_minutes", 30),
                buffer_minutes=w.get("buffer_minutes", 0),
            )
            for w in windows
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return rows

    async def get_for_day(
        self, tenant: TenantContext, *, day_of_week: int, staff_id: uuid.UUID | None = None
    ) -> MerchantAvailability | None:
        staff_filter = (
            MerchantAvailability.staff_id.is_(None)
            if staff_id is None
            else MerchantAvailability.staff_id == staff_id
        )
        result = await self._session.execute(
            select(MerchantAvailability).where(
                MerchantAvailability.merchant_id == tenant.merchant_id,
                MerchantAvailability.day_of_week == day_of_week,
                staff_filter,
            )
        )
        return result.scalar_one_or_none()

    async def list(self, tenant: TenantContext) -> list[MerchantAvailability]:
        result = await self._session.execute(
            select(MerchantAvailability)
            .where(
                MerchantAvailability.merchant_id == tenant.merchant_id,
                MerchantAvailability.staff_id.is_(None),
            )
            .order_by(MerchantAvailability.day_of_week.asc())
        )
        return list(result.scalars().all())
