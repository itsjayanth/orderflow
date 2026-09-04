import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from customers.domain.models import Address, Customer, MerchantCustomerCounter
from customers.domain.phone import normalize_whatsapp_id
from shared.tenant import TenantContext


class CustomerWhatsAppNumberConflictError(Exception):
    pass


def _canonical_whatsapp_number(whatsapp_number: str) -> str:
    """Every write/read of Customer.whatsapp_number goes through this, so a
    number that reaches this repository as "+91 98765-43210" and one that
    reaches it as "919876543210" (Meta's own inbound shape -- see
    customers.domain.phone.normalize_whatsapp_id) always resolve to the
    same Customer row instead of silently creating two. Falls back to the
    raw string, unnormalized, when normalize_whatsapp_id can't make sense
    of it (out of E.164's digit-count range) -- storing something
    malformed as-is beats refusing to create the customer/order at all
    over a formatting quirk; this repeats this codebase's existing
    "un-normalized input" behavior for that edge case rather than
    introducing a new failure mode."""
    return normalize_whatsapp_id(whatsapp_number) or whatsapp_number


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
        always return the same Customer row, never a duplicate -- including
        across formatting differences in whatsapp_number itself (see
        _canonical_whatsapp_number), so a native Flow's digit-only
        flow_token and a webview's "+"-prefixed submission for the same
        person still land on one row. This is the method Phase 6's
        Conversation Handler calls on every inbound message."""
        existing = await self.get_by_whatsapp_number(tenant, whatsapp_number)
        if existing is not None:
            return existing

        customer_number = await self._next_customer_number(tenant.merchant_id)
        customer = Customer(
            merchant_id=tenant.merchant_id,
            customer_number=customer_number,
            whatsapp_number=_canonical_whatsapp_number(whatsapp_number),
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
        last_payment_method: str | None = None,
    ) -> None:
        """Refreshes a returning customer's name, delivery-contact
        preference, and last-used payment method from what they just
        submitted at checkout -- find_or_create() deliberately only sets
        these at creation, so without this a correction (or a changed
        contact-number/payment choice) would never stick for next time.
        Always overwrites default_contact_phone (None is a real,
        meaningful value here: "go back to using my WhatsApp number"), but
        leaves display_name alone when None is passed, since not every
        caller collects a name. last_payment_method follows display_name's
        "only overwrite when given" rule too, for the same reason: not
        every caller (e.g. a future non-checkout writer) necessarily has
        one to report."""
        if display_name is not None:
            customer.display_name = display_name
        customer.default_contact_phone = default_contact_phone
        if last_payment_method is not None:
            customer.last_payment_method = last_payment_method
        await self._session.flush()

    async def set_marketing_opt_out(self, customer: Customer, *, opted_out: bool) -> None:
        """The only writer of Customer.marketing_opt_out/marketing_opt_out_at
        -- driven exclusively by the customer's own STOP/START message
        (conversation/domain/handler.py's Intent.OPT_OUT/OPT_IN branch), per
        customers/api/router.py's read-only exposure of these fields: a
        merchant can't flip this from the dashboard, only the customer can."""
        customer.marketing_opt_out = opted_out
        customer.marketing_opt_out_at = datetime.datetime.now(datetime.UTC)
        await self._session.flush()

    async def update_profile_from_appointment(
        self,
        customer: Customer,
        *,
        display_name: str | None,
        email: str | None,
    ) -> None:
        """Refreshes a returning customer's name/email from what they just
        confirmed on an appointment booking -- mirrors
        update_contact_details's role for checkout, but deliberately
        doesn't touch default_contact_phone (appointments have no
        "different contact number" concept, see the appointment Flow's own
        docs) so booking an appointment can never clobber a contact-number
        preference the order flow set. Only overwrites a field when given
        a non-empty value: a typo fix or a first-time email should stick,
        but perform_booking always has *some* name (falls back to the
        WhatsApp profile name) and always has an email (required on the
        booking form), so in practice this only ever leaves fields alone
        for callers that don't collect them at all."""
        if display_name:
            customer.display_name = display_name
        if email:
            customer.email = email
        await self._session.flush()

    async def get_by_whatsapp_number(
        self, tenant: TenantContext, whatsapp_number: str
    ) -> Customer | None:
        """(merchant_id, whatsapp_number) match after normalizing
        whatsapp_number the same way find_or_create/create do (see
        _canonical_whatsapp_number) -- also used by
        customers.domain.identity_resolution, the shared entrypoint both
        the order and appointment flows prefill from."""
        result = await self._session.execute(
            select(Customer).where(
                Customer.merchant_id == tenant.merchant_id,
                Customer.whatsapp_number == _canonical_whatsapp_number(whatsapp_number),
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
            whatsapp_number=_canonical_whatsapp_number(whatsapp_number),
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
