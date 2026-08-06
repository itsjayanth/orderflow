import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from customers.domain.models import Address, Customer
from shared.tenant import TenantContext


class CustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_or_create(
        self,
        tenant: TenantContext,
        whatsapp_number: str,
        display_name: str | None = None,
    ) -> Customer:
        """Idempotent: repeated calls with the same (merchant_id, whatsapp_number)
        always return the same Customer row, never a duplicate. This is the
        method Phase 6's Conversation Handler calls on every inbound message."""
        existing = await self._get_by_whatsapp_number(tenant, whatsapp_number)
        if existing is not None:
            return existing

        customer = Customer(
            merchant_id=tenant.merchant_id,
            whatsapp_number=whatsapp_number,
            display_name=display_name,
        )
        self._session.add(customer)
        await self._session.flush()
        return customer

    async def _get_by_whatsapp_number(
        self, tenant: TenantContext, whatsapp_number: str
    ) -> Customer | None:
        result = await self._session.execute(
            select(Customer).where(
                Customer.merchant_id == tenant.merchant_id,
                Customer.whatsapp_number == whatsapp_number,
            )
        )
        return result.scalar_one_or_none()

    async def list(self, tenant: TenantContext) -> list[Customer]:
        result = await self._session.execute(
            select(Customer)
            .where(Customer.merchant_id == tenant.merchant_id)
            .order_by(Customer.first_seen_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, tenant: TenantContext, customer_id: uuid.UUID) -> Customer | None:
        result = await self._session.execute(
            select(Customer).where(
                Customer.customer_id == customer_id,
                Customer.merchant_id == tenant.merchant_id,
            )
        )
        return result.scalar_one_or_none()


class AddressRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_customer(
        self, tenant: TenantContext, customer_id: uuid.UUID
    ) -> list[Address]:
        result = await self._session.execute(
            select(Address)
            .where(
                Address.merchant_id == tenant.merchant_id,
                Address.customer_id == customer_id,
            )
            .order_by(Address.created_at.asc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        tenant: TenantContext,
        customer_id: uuid.UUID,
        label: str,
        line1: str,
        city: str,
        pincode: str,
        line2: str | None = None,
        landmark: str | None = None,
        geo_lat: float | None = None,
        geo_long: float | None = None,
        is_default: bool = False,
    ) -> Address:
        address = Address(
            merchant_id=tenant.merchant_id,
            customer_id=customer_id,
            label=label,
            line1=line1,
            line2=line2,
            landmark=landmark,
            city=city,
            pincode=pincode,
            geo_lat=geo_lat,
            geo_long=geo_long,
            is_default=is_default,
        )
        self._session.add(address)
        await self._session.flush()
        return address
