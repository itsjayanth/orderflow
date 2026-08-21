import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from customers.domain.models import Address, Customer, MerchantCustomerCounter
from shared.tenant import TenantContext


class CustomerWhatsAppNumberConflictError(Exception):
    pass


class CustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _next_customer_number(self, merchant_id: uuid.UUID) -> int:
        """Atomic per-merchant counter upsert -- see
        orders/adapters/repository.py's `_next_order_number` for the exact
        same pattern and why it's safe under concurrent creation."""
        stmt = (
            pg_insert(MerchantCustomerCounter)
            .values(merchant_id=merchant_id, next_customer_number=2)
            .on_conflict_do_update(
                index_elements=[MerchantCustomerCounter.merchant_id],
                set_={
                    "next_customer_number": (
                        MerchantCustomerCounter.__table__.c.next_customer_number + 1
                    )
                },
            )
            .returning(MerchantCustomerCounter.next_customer_number)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() - 1

    async def find_or_create(
        self,
        tenant: TenantContext,
        whatsapp_number: str,
        display_name: str | None = None,
    ) -> Customer:
        """Idempotent: repeated calls with the same (merchant_id, whatsapp_number)
        always return the same Customer row, never a duplicate. This is the
        method Phase 6's Conversation Handler calls on every inbound message."""
        existing = await self.get_by_whatsapp_number(tenant, whatsapp_number)
        if existing is not None:
            return existing

        customer_number = await self._next_customer_number(tenant.merchant_id)
        customer = Customer(
            merchant_id=tenant.merchant_id,
            customer_number=customer_number,
            whatsapp_number=whatsapp_number,
            display_name=display_name,
        )
        self._session.add(customer)
        await self._session.flush()
        return customer

    async def update_contact_details(
        self,
        customer: Customer,
        *,
        display_name: str | None,
        default_contact_phone: str | None,
    ) -> None:
        """Refreshes a returning customer's name and delivery-contact
        preference from what they just submitted at checkout --
        find_or_create() deliberately only sets these at creation, so
        without this a correction (or a changed contact-number choice)
        would never stick for next time. Always overwrites
        default_contact_phone (None is a real, meaningful value here: "go
        back to using my WhatsApp number"), but leaves display_name alone
        when None is passed, since not every caller collects a name."""
        if display_name is not None:
            customer.display_name = display_name
        customer.default_contact_phone = default_contact_phone
        await self._session.flush()

    async def get_by_whatsapp_number(
        self, tenant: TenantContext, whatsapp_number: str
    ) -> Customer | None:
        """Exact (merchant_id, whatsapp_number) match -- also used by the
        public ordering webview's customer-lookup endpoint to prefill a
        returning customer's name/address without asking again."""
        result = await self._session.execute(
            select(Customer).where(
                Customer.merchant_id == tenant.merchant_id,
                Customer.whatsapp_number == whatsapp_number,
            )
        )
        return result.scalar_one_or_none()

    async def list(self, tenant: TenantContext, include_inactive: bool = False) -> list[Customer]:
        stmt = (
            select(Customer)
            .where(Customer.merchant_id == tenant.merchant_id)
            .order_by(Customer.first_seen_at.desc())
        )
        if not include_inactive:
            stmt = stmt.where(Customer.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, tenant: TenantContext, customer_id: uuid.UUID) -> Customer | None:
        result = await self._session.execute(
            select(Customer).where(
                Customer.customer_id == customer_id,
                Customer.merchant_id == tenant.merchant_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        tenant: TenantContext,
        *,
        whatsapp_number: str,
        display_name: str | None = None,
        default_contact_phone: str | None = None,
        email: str | None = None,
    ) -> Customer:
        """Staff-initiated creation from the dashboard's Customers tab --
        distinct from find_or_create (the WhatsApp-inbound entry point):
        always either inserts a new row or raises, rather than silently
        returning an existing match, since a staff member entering a
        number that's already a customer is almost certainly a mistake
        worth surfacing rather than swallowing."""
        if await self.get_by_whatsapp_number(tenant, whatsapp_number) is not None:
            raise CustomerWhatsAppNumberConflictError(whatsapp_number)

        customer_number = await self._next_customer_number(tenant.merchant_id)
        customer = Customer(
            merchant_id=tenant.merchant_id,
            customer_number=customer_number,
            whatsapp_number=whatsapp_number,
            display_name=display_name,
            default_contact_phone=default_contact_phone,
            email=email,
        )
        self._session.add(customer)
        await self._session.flush()
        return customer

    async def update(
        self,
        tenant: TenantContext,
        customer_id: uuid.UUID,
        *,
        display_name: str | None = None,
        default_contact_phone: str | None = None,
        email: str | None = None,
        is_active: bool | None = None,
    ) -> Customer | None:
        """Dashboard-driven edit/deactivate. Unlike update_contact_details
        (checkout's writer, which always overwrites default_contact_phone
        since None is meaningful there), this only touches fields the
        caller actually passed -- and also covers is_active, the
        deactivate/reactivate ("delete") toggle. Deliberately never
        touches whatsapp_number: that's the identity inbound WhatsApp
        messages are matched on (find_or_create), so it isn't
        dashboard-editable."""
        customer = await self.get(tenant, customer_id)
        if customer is None:
            return None

        if display_name is not None:
            customer.display_name = display_name
        if default_contact_phone is not None:
            customer.default_contact_phone = default_contact_phone
        if email is not None:
            customer.email = email
        if is_active is not None:
            customer.is_active = is_active

        await self._session.flush()
        return customer


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

    async def get_primary_for_customer(
        self, tenant: TenantContext, customer_id: uuid.UUID
    ) -> Address | None:
        """The address the ordering webview should prefill for a returning
        customer: whichever is marked default, falling back to the most
        recently added one."""
        result = await self._session.execute(
            select(Address)
            .where(
                Address.merchant_id == tenant.merchant_id,
                Address.customer_id == customer_id,
            )
            .order_by(Address.is_default.desc(), Address.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

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
