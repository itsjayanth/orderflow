import asyncio
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from customers.adapters.repository import AddressRepository, CustomerRepository
from customers.domain.identity_resolution import resolve_customer_by_whatsapp_id
from customers.domain.phone import normalize_whatsapp_id
from identity.adapters.repository import MerchantRepository
from shared.tenant import TenantContext

# --- normalize_whatsapp_id ---------------------------------------------


def test_normalize_whatsapp_id_strips_plus_spaces_and_dashes() -> None:
    assert normalize_whatsapp_id("+91 98765-43210") == "919876543210"


def test_normalize_whatsapp_id_passes_through_already_digit_only() -> None:
    assert normalize_whatsapp_id("919876543210") == "919876543210"


def test_normalize_whatsapp_id_returns_none_for_non_string() -> None:
    assert normalize_whatsapp_id(None) is None
    assert normalize_whatsapp_id(12345678901) is None
    assert normalize_whatsapp_id({"flow_token": "919876543210"}) is None


def test_normalize_whatsapp_id_returns_none_for_empty_string() -> None:
    assert normalize_whatsapp_id("") is None


def test_normalize_whatsapp_id_returns_none_when_too_short() -> None:
    assert normalize_whatsapp_id("12345") is None  # 5 digits, below E.164's 7-digit floor


def test_normalize_whatsapp_id_returns_none_when_too_long() -> None:
    assert normalize_whatsapp_id("1234567890123456") is None  # 16 digits, above E.164's ceiling


# --- resolve_customer_by_whatsapp_id -------------------------------------


async def _make_tenant(
    db_session: AsyncSession, business_name: str = "Test Business"
) -> TenantContext:
    merchant = await MerchantRepository(db_session).create(
        business_name=business_name, owner_contact=f"{uuid.uuid4()}@example.com"
    )
    return TenantContext(merchant_id=merchant.merchant_id)


async def test_resolve_customer_returns_none_for_malformed_whatsapp_id(
    db_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(db_session)

    resolved = await resolve_customer_by_whatsapp_id(db_session, tenant, "not-a-phone-number!!")

    assert resolved is None


async def test_resolve_customer_returns_none_for_missing_whatsapp_id(
    db_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(db_session)

    assert await resolve_customer_by_whatsapp_id(db_session, tenant, None) is None
    assert await resolve_customer_by_whatsapp_id(db_session, tenant, "") is None


async def test_resolve_customer_returns_none_for_new_customer(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)

    resolved = await resolve_customer_by_whatsapp_id(db_session, tenant, "919876543210")

    assert resolved is None


async def test_resolve_customer_returns_saved_customer(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    created = await CustomerRepository(db_session).find_or_create(
        tenant, "919876543210", display_name="Asha"
    )
    await db_session.commit()

    resolved = await resolve_customer_by_whatsapp_id(db_session, tenant, "919876543210")

    assert resolved is not None
    assert resolved.customer.customer_id == created.customer_id
    assert resolved.customer.display_name == "Asha"
    assert resolved.address is None  # include_address defaults to False


async def test_resolve_customer_normalizes_before_lookup(db_session: AsyncSession) -> None:
    """A "+"-formatted lookup id still finds a customer stored (normalized)
    without the "+"."""
    tenant = await _make_tenant(db_session)
    created = await CustomerRepository(db_session).find_or_create(
        tenant, "919876543210", display_name="Asha"
    )
    await db_session.commit()

    resolved = await resolve_customer_by_whatsapp_id(db_session, tenant, "+91 98765 43210")

    assert resolved is not None
    assert resolved.customer.customer_id == created.customer_id


async def test_resolve_customer_includes_address_when_requested(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "919876543210")
    await AddressRepository(db_session).create(
        tenant,
        customer.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
        is_default=True,
    )
    await db_session.commit()

    resolved = await resolve_customer_by_whatsapp_id(
        db_session, tenant, "919876543210", include_address=True
    )

    assert resolved is not None
    assert resolved.address is not None
    assert resolved.address.line1 == "12 MG Road"


async def test_resolve_customer_scoped_per_merchant(db_session: AsyncSession) -> None:
    tenant_a = await _make_tenant(db_session, business_name="A")
    tenant_b = await _make_tenant(db_session, business_name="B")
    await CustomerRepository(db_session).find_or_create(
        tenant_a, "919876543210", display_name="Asha"
    )
    await db_session.commit()

    resolved = await resolve_customer_by_whatsapp_id(db_session, tenant_b, "919876543210")

    assert resolved is None


async def test_resolve_customer_falls_back_within_latency_budget_on_lookup_timeout(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lookup that hangs must never block the flow -- resolve_customer_by_
    whatsapp_id wraps the DB call in a timeout and falls back to None. This
    asserts the fallback actually happens *within* that budget (with slack
    for scheduling jitter), not that it eventually completes."""
    tenant = await _make_tenant(db_session)
    await CustomerRepository(db_session).find_or_create(tenant, "919876543210", display_name="Asha")
    await db_session.commit()

    async def _hangs_forever(self: CustomerRepository, tenant: TenantContext, whatsapp_number: str):
        await asyncio.sleep(3600)

    monkeypatch.setattr(CustomerRepository, "get_by_whatsapp_number", _hangs_forever)

    loop = asyncio.get_event_loop()
    started = loop.time()
    resolved = await resolve_customer_by_whatsapp_id(db_session, tenant, "919876543210")
    elapsed = loop.time() - started

    assert resolved is None
    assert elapsed < 5.0  # well under the hang's 3600s, generous slack over the 2s budget


async def test_resolve_customer_falls_back_on_lookup_exception(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant = await _make_tenant(db_session)

    async def _raises(self: CustomerRepository, tenant: TenantContext, whatsapp_number: str):
        raise RuntimeError("db connection lost")

    monkeypatch.setattr(CustomerRepository, "get_by_whatsapp_number", _raises)

    resolved = await resolve_customer_by_whatsapp_id(db_session, tenant, "919876543210")

    assert resolved is None
