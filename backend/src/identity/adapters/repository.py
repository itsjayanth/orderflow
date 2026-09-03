import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from identity.domain.models import Merchant, MerchantVertical, StaffUser, validate_vertical_flags


class MerchantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, business_name: str, owner_contact: str) -> Merchant:
        merchant = Merchant(business_name=business_name, owner_contact=owner_contact)
        self._session.add(merchant)
        await self._session.flush()
        return merchant

    async def get(self, merchant_id: uuid.UUID) -> Merchant | None:
        return await self._session.get(Merchant, merchant_id)

    async def set_vertical_flags(
        self, merchant_id: uuid.UUID, *, restaurant_enabled: bool, appointment_enabled: bool
    ) -> Merchant:
        """The only writer for both flags -- called from the onboarding
        wizard's first step and, later, from Settings' "Business types"
        section, both through the same PUT /api/v1/onboarding/verticals
        endpoint. No one-time/immutability guard (VERTICAL_TOGGLE_PLAN.md
        deliberately retires Phase 10's "exactly one, forever" rule) -- just
        the shared invariant validator, so both entry points get identical
        behavior."""
        validate_vertical_flags(
            restaurant_enabled=restaurant_enabled, appointment_enabled=appointment_enabled
        )
        merchant = await self._session.get(Merchant, merchant_id)
        assert merchant is not None
        merchant.restaurant_enabled = restaurant_enabled
        merchant.appointment_enabled = appointment_enabled
        await self._session.flush()
        return merchant

    async def update_timezone(self, merchant_id: uuid.UUID, timezone: str) -> Merchant:
        """Dashboard availability-settings save -- see
        AppointmentAvailabilitySettingsUpdate. A missing merchant here is a
        caller bug (the API layer resolves merchant_id from an
        authenticated TenantContext, which can't name a merchant that
        doesn't exist) -- so this doesn't guard against None, matching the
        simplicity of MerchantRepository.get's contract elsewhere in this
        class."""
        merchant = await self._session.get(Merchant, merchant_id)
        assert merchant is not None
        merchant.timezone = timezone
        await self._session.flush()
        return merchant

    async def update_reminder_offsets_hours(
        self, merchant_id: uuid.UUID, reminder_offsets_hours: list[int]
    ) -> Merchant:
        """Same dashboard availability-settings save as update_timezone --
        both are set together by the one PUT
        /appointment-availability endpoint."""
        merchant = await self._session.get(Merchant, merchant_id)
        assert merchant is not None
        merchant.reminder_offsets_hours = reminder_offsets_hours
        await self._session.flush()
        return merchant

    async def list_enabled_for_vertical(self, vertical: MerchantVertical) -> list[Merchant]:
        """Every merchant with the given vertical's flag on -- used by the
        reminder scan (shared/scheduler.py's send_due_appointment_reminders)
        to find appointment-enabled merchants to check. Not tenant-scoped by
        design, same rationale as StaffUserRepository below: this runs from
        the scheduler, not a per-request tenant context."""
        column = (
            Merchant.appointment_enabled
            if vertical == MerchantVertical.APPOINTMENT
            else Merchant.restaurant_enabled
        )
        result = await self._session.execute(select(Merchant).where(column.is_(True)))
        return list(result.scalars().all())


class StaffUserRepository:
    """Not tenant-scoped by TenantContext: login/registration precede tenant
    resolution, since the token that carries the tenant doesn't exist yet."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        merchant_id: uuid.UUID,
        name: str,
        email_or_phone: str,
        password_hash: str,
        role: str = "owner",
    ) -> StaffUser:
        staff_user = StaffUser(
            merchant_id=merchant_id,
            name=name,
            email_or_phone=email_or_phone,
            password_hash=password_hash,
            role=role,
        )
        self._session.add(staff_user)
        await self._session.flush()
        return staff_user

    async def get_by_email_or_phone(self, email_or_phone: str) -> StaffUser | None:
        result = await self._session.execute(
            select(StaffUser).where(StaffUser.email_or_phone == email_or_phone)
        )
        return result.scalar_one_or_none()

    async def get(self, staff_user_id: uuid.UUID) -> StaffUser | None:
        return await self._session.get(StaffUser, staff_user_id)
