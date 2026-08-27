import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from identity.domain.models import Merchant, StaffUser


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

    async def update_appointment_booking_enabled(
        self, merchant_id: uuid.UUID, enabled: bool
    ) -> Merchant:
        """Dashboard Settings page toggle for the Appointment Booking
        feature. A missing merchant here is a caller bug (the API layer
        resolves merchant_id from an authenticated TenantContext, which
        can't name a merchant that doesn't exist) -- so this doesn't guard
        against None, matching the simplicity of MerchantRepository.get's
        contract elsewhere in this class."""
        merchant = await self._session.get(Merchant, merchant_id)
        assert merchant is not None
        merchant.appointment_booking_enabled = enabled
        await self._session.flush()
        return merchant


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
