import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import ItemRepository
from customers.adapters.repository import AddressInUseError, AddressRepository, CustomerRepository
from customers.domain.models import Customer
from identity.adapters.repository import MerchantRepository
from orders.adapters.repository import OrderItemInput, OrderRepository
from shared.tenant import TenantContext


async def _make_tenant(
    db_session: AsyncSession, business_name: str = "Test Business"
) -> TenantContext:
    """Repository-level tests need a real Merchant row since merchant_id is a FK."""
    merchant = await MerchantRepository(db_session).create(
        business_name=business_name, owner_contact=f"{uuid.uuid4()}@example.com"
    )
    return TenantContext(merchant_id=merchant.merchant_id)


async def _register(client: AsyncClient, owner_contact: str = "owner@example.com") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "business_name": "Test Business",
            "owner_name": "Jane Owner",
            "owner_contact": owner_contact,
            "password": "correct-horse-battery-staple",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _tenant_for(client: AsyncClient, tokens: dict) -> TenantContext:
    me = await client.get("/api/v1/auth/me", headers=_auth_headers(tokens))
    assert me.status_code == 200
    return TenantContext(merchant_id=uuid.UUID(me.json()["merchant"]["merchant_id"]))


# --- find_or_create idempotency (repository level, per the plan's DoD) ---


async def test_find_or_create_idempotent(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    repo = CustomerRepository(db_session)

    first = await repo.find_or_create(tenant, "+919876543210", display_name="Asha")
    second = await repo.find_or_create(tenant, "+919876543210", display_name="Asha (again)")

    assert first.customer_id == second.customer_id

    # Stored normalized (no "+") -- see customers.domain.phone.normalize_whatsapp_id
    # -- so this queries the canonical form, not the raw "+"-prefixed input.
    result = await db_session.execute(
        select(Customer).where(
            Customer.merchant_id == tenant.merchant_id,
            Customer.whatsapp_number == "919876543210",
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 1


async def test_find_or_create_idempotent_across_whatsapp_number_formatting(
    db_session: AsyncSession,
) -> None:
    """A native Flow's flow_token ("919876543210", Meta's own inbound shape)
    and a webview's client-submitted "+91 98765-43210" for the same person
    must resolve to the same Customer row, not create two -- see
    customers.domain.phone.normalize_whatsapp_id's docstring."""
    tenant = await _make_tenant(db_session)
    repo = CustomerRepository(db_session)

    from_native_flow = await repo.find_or_create(tenant, "919876543210", display_name="Asha")
    from_webview = await repo.find_or_create(tenant, "+91 98765-43210", display_name="Asha")

    assert from_native_flow.customer_id == from_webview.customer_id


async def test_customer_numbers_increment_sequentially_per_merchant(
    db_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(db_session)
    repo = CustomerRepository(db_session)

    first = await repo.find_or_create(tenant, "+919876543210", display_name="Asha")
    second = await repo.find_or_create(tenant, "+919876543211", display_name="Priya")
    third = await repo.find_or_create(tenant, "+919876543212", display_name="Vikram")

    assert [first.customer_number, second.customer_number, third.customer_number] == [1, 2, 3]


async def test_customer_numbers_isolated_per_merchant(db_session: AsyncSession) -> None:
    tenant_a = await _make_tenant(db_session, business_name="Business A")
    tenant_b = await _make_tenant(db_session, business_name="Business B")
    repo = CustomerRepository(db_session)

    customer_a1 = await repo.find_or_create(tenant_a, "+919876543210")
    customer_b1 = await repo.find_or_create(tenant_b, "+919876543210")
    customer_a2 = await repo.find_or_create(tenant_a, "+919876543211")

    assert customer_a1.customer_number == 1
    assert customer_b1.customer_number == 1
    assert customer_a2.customer_number == 2


async def test_find_or_create_different_merchants_get_different_customers(
    db_session: AsyncSession,
) -> None:
    tenant_a = await _make_tenant(db_session, "Business A")
    tenant_b = await _make_tenant(db_session, "Business B")
    repo = CustomerRepository(db_session)

    customer_a = await repo.find_or_create(tenant_a, "+919876543210")
    customer_b = await repo.find_or_create(tenant_b, "+919876543210")

    assert customer_a.customer_id != customer_b.customer_id


# --- Address repository ---


async def test_address_create_and_list_for_customer(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")

    address_repo = AddressRepository(db_session)
    await address_repo.create(
        tenant,
        customer.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
        is_default=True,
    )
    await address_repo.create(
        tenant,
        customer.customer_id,
        label="Work",
        line1="45 Residency Road",
        city="Bengaluru",
        pincode="560025",
    )

    addresses = await address_repo.list_for_customer(tenant, customer.customer_id)
    assert len(addresses) == 2
    assert {a.label for a in addresses} == {"Home", "Work"}


async def test_addresses_scoped_to_customer(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    customer_repo = CustomerRepository(db_session)
    customer_a = await customer_repo.find_or_create(tenant, "+919876543210")
    customer_b = await customer_repo.find_or_create(tenant, "+919876543211")

    address_repo = AddressRepository(db_session)
    await address_repo.create(
        tenant, customer_a.customer_id, label="Home", line1="1 A St", city="Bengaluru", pincode="1"
    )

    addresses_for_b = await address_repo.list_for_customer(tenant, customer_b.customer_id)
    assert addresses_for_b == []


# --- API endpoints ---


async def test_list_customers_empty(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.get("/api/v1/customers", headers=_auth_headers(tokens))

    assert response.status_code == 200
    assert response.json() == []


async def test_list_customers_returns_seeded_customer(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await CustomerRepository(db_session).find_or_create(
        tenant, "+919876543210", display_name="Asha"
    )
    await db_session.commit()

    response = await client.get("/api/v1/customers", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["display_name"] == "Asha"
    # Stored normalized (no "+") -- see customers.domain.phone.normalize_whatsapp_id.
    assert body[0]["whatsapp_number"] == "919876543210"
    assert body[0]["customer_number"] == 1


async def test_get_customer_detail_includes_addresses(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
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

    response = await client.get(
        f"/api/v1/customers/{customer.customer_id}", headers=_auth_headers(tokens)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["customer_id"] == str(customer.customer_id)
    assert len(body["addresses"]) == 1
    assert body["addresses"][0]["label"] == "Home"


async def test_get_customer_not_found(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.get(f"/api/v1/customers/{uuid.uuid4()}", headers=_auth_headers(tokens))

    assert response.status_code == 404


async def test_customers_isolated_between_merchants(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    tenant_a = await _tenant_for(client, tokens_a)
    tokens_b = await _register(client, owner_contact="owner-b@example.com")

    customer_a = await CustomerRepository(db_session).find_or_create(tenant_a, "+919876543210")
    await db_session.commit()

    # Merchant B's token cannot list merchant A's customer.
    list_response = await client.get("/api/v1/customers", headers=_auth_headers(tokens_b))
    assert list_response.status_code == 200
    assert list_response.json() == []

    # Merchant B's token cannot fetch merchant A's customer by id either.
    detail_response = await client.get(
        f"/api/v1/customers/{customer_a.customer_id}", headers=_auth_headers(tokens_b)
    )
    assert detail_response.status_code == 404

    # Merchant A's own token can still see it.
    own_detail_response = await client.get(
        f"/api/v1/customers/{customer_a.customer_id}", headers=_auth_headers(tokens_a)
    )
    assert own_detail_response.status_code == 200


# --- Dashboard CRUD: create / update / deactivate ------------------------


async def test_create_customer(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.post(
        "/api/v1/customers",
        json={
            "whatsapp_number": "+919876543210",
            "display_name": "Walk-in Asha",
            "email": "asha@example.com",
        },
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 201
    body = response.json()
    # Stored normalized (no "+") -- see customers.domain.phone.normalize_whatsapp_id.
    assert body["whatsapp_number"] == "919876543210"
    assert body["display_name"] == "Walk-in Asha"
    assert body["email"] == "asha@example.com"
    assert body["customer_number"] == 1
    assert body["is_active"] is True


async def test_update_customer_email(client: AsyncClient, db_session: AsyncSession) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/customers/{customer.customer_id}",
        json={"email": "asha@example.com"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    assert response.json()["email"] == "asha@example.com"


async def test_create_customer_duplicate_whatsapp_number_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    await db_session.commit()

    response = await client.post(
        "/api/v1/customers",
        json={"whatsapp_number": "+919876543210"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 409


async def test_update_customer_display_name_and_contact_phone(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/customers/{customer.customer_id}",
        json={"display_name": "Asha Rao", "default_contact_phone": "+919876500000"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Asha Rao"
    assert body["default_contact_phone"] == "+919876500000"
    # whatsapp_number is never dashboard-editable -- it's the identity
    # inbound WhatsApp messages are matched on. Stored normalized (no "+"),
    # see customers.domain.phone.normalize_whatsapp_id.
    assert body["whatsapp_number"] == "919876543210"


async def test_update_customer_not_found(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.patch(
        f"/api/v1/customers/{uuid.uuid4()}",
        json={"display_name": "Nobody"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 404


async def test_deactivate_customer_is_excluded_from_default_list(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer = await CustomerRepository(db_session).find_or_create(
        tenant, "+919876543210", display_name="Asha"
    )
    await db_session.commit()

    deactivate_response = await client.patch(
        f"/api/v1/customers/{customer.customer_id}",
        json={"is_active": False},
        headers=_auth_headers(tokens),
    )
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    list_response = await client.get("/api/v1/customers", headers=_auth_headers(tokens))
    assert list_response.json() == []

    include_inactive_response = await client.get(
        "/api/v1/customers", params={"include_inactive": True}, headers=_auth_headers(tokens)
    )
    assert len(include_inactive_response.json()) == 1
    assert include_inactive_response.json()[0]["is_active"] is False


async def test_reactivate_customer(client: AsyncClient, db_session: AsyncSession) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    await db_session.commit()

    await client.patch(
        f"/api/v1/customers/{customer.customer_id}",
        json={"is_active": False},
        headers=_auth_headers(tokens),
    )
    reactivate_response = await client.patch(
        f"/api/v1/customers/{customer.customer_id}",
        json={"is_active": True},
        headers=_auth_headers(tokens),
    )

    assert reactivate_response.status_code == 200
    assert reactivate_response.json()["is_active"] is True
    list_response = await client.get("/api/v1/customers", headers=_auth_headers(tokens))
    assert len(list_response.json()) == 1


async def _seed_order_referencing_address(
    db_session: AsyncSession, tenant: TenantContext, customer: Customer, address_id: uuid.UUID
):
    item = await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    order = await OrderRepository(db_session).create(
        tenant,
        customer_id=customer.customer_id,
        order_type="delivery",
        payment_method="online",
        payment_status="paid",
        fulfillment_status="new",
        delivery_address_id=address_id,
        items=[
            OrderItemInput(
                item_id=item.item_id,
                name_snapshot=item.name,
                price_snapshot=item.price,
                quantity=1,
            )
        ],
    )
    await db_session.commit()
    return order


# --- AddressRepository.update / delete --------------------------------------


async def test_address_update_partial_fields(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    address_repo = AddressRepository(db_session)
    address = await address_repo.create(
        tenant,
        customer.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
    )

    updated = await address_repo.update(
        tenant, customer.customer_id, address.address_id, line1="14 MG Road", city="Bengaluru"
    )

    assert updated is not None
    assert updated.line1 == "14 MG Road"
    # Untouched fields are left alone.
    assert updated.label == "Home"
    assert updated.pincode == "560001"


async def test_address_update_is_default_exclusivity(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    address_repo = AddressRepository(db_session)
    home = await address_repo.create(
        tenant,
        customer.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
        is_default=True,
    )
    work = await address_repo.create(
        tenant,
        customer.customer_id,
        label="Work",
        line1="45 Residency Road",
        city="Bengaluru",
        pincode="560025",
    )

    await address_repo.update(tenant, customer.customer_id, work.address_id, is_default=True)

    addresses = {
        a.address_id: a for a in await address_repo.list_for_customer(tenant, customer.customer_id)
    }
    assert addresses[work.address_id].is_default is True
    assert addresses[home.address_id].is_default is False


async def test_address_update_not_found_returns_none(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    address_repo = AddressRepository(db_session)

    result = await address_repo.update(tenant, customer.customer_id, uuid.uuid4(), label="Nope")

    assert result is None


async def test_address_delete_removes_address_with_no_orders(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    address_repo = AddressRepository(db_session)
    address = await address_repo.create(
        tenant,
        customer.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
    )

    deleted = await address_repo.delete(tenant, customer.customer_id, address.address_id)

    assert deleted is True
    assert await address_repo.list_for_customer(tenant, customer.customer_id) == []


async def test_address_delete_raises_when_referenced_by_order(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    address_repo = AddressRepository(db_session)
    address = await address_repo.create(
        tenant,
        customer.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
    )
    await _seed_order_referencing_address(db_session, tenant, customer, address.address_id)

    with pytest.raises(AddressInUseError):
        await address_repo.delete(tenant, customer.customer_id, address.address_id)

    # Address left intact.
    remaining = await address_repo.list_for_customer(tenant, customer.customer_id)
    assert len(remaining) == 1


# --- Address API endpoints ---------------------------------------------------


async def test_update_address_api(client: AsyncClient, db_session: AsyncSession) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    address = await AddressRepository(db_session).create(
        tenant,
        customer.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
    )
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/customers/{customer.customer_id}/addresses/{address.address_id}",
        json={"line1": "14 MG Road"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    assert response.json()["line1"] == "14 MG Road"

    get_response = await client.get(
        f"/api/v1/customers/{customer.customer_id}", headers=_auth_headers(tokens)
    )
    assert get_response.json()["addresses"][0]["line1"] == "14 MG Road"


async def test_update_address_not_found_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/customers/{customer.customer_id}/addresses/{uuid.uuid4()}",
        json={"line1": "Nope"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 404


async def test_update_address_wrong_customer_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer_a = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    customer_b = await CustomerRepository(db_session).find_or_create(tenant, "+919876543211")
    address = await AddressRepository(db_session).create(
        tenant,
        customer_a.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
    )
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/customers/{customer_b.customer_id}/addresses/{address.address_id}",
        json={"line1": "Hijacked"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 404


async def test_update_address_wrong_tenant_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens_a = await _register(client, owner_contact="addr-a@example.com")
    tenant_a = await _tenant_for(client, tokens_a)
    tokens_b = await _register(client, owner_contact="addr-b@example.com")
    customer_a = await CustomerRepository(db_session).find_or_create(tenant_a, "+919876543210")
    address = await AddressRepository(db_session).create(
        tenant_a,
        customer_a.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
    )
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/customers/{customer_a.customer_id}/addresses/{address.address_id}",
        json={"line1": "Hijacked"},
        headers=_auth_headers(tokens_b),
    )

    assert response.status_code == 404


async def test_delete_address_api(client: AsyncClient, db_session: AsyncSession) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    address = await AddressRepository(db_session).create(
        tenant,
        customer.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
    )
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/customers/{customer.customer_id}/addresses/{address.address_id}",
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 204

    get_response = await client.get(
        f"/api/v1/customers/{customer.customer_id}", headers=_auth_headers(tokens)
    )
    assert get_response.json()["addresses"] == []


async def test_delete_address_not_found_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/customers/{customer.customer_id}/addresses/{uuid.uuid4()}",
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 404


async def test_delete_address_wrong_customer_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer_a = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    customer_b = await CustomerRepository(db_session).find_or_create(tenant, "+919876543211")
    address = await AddressRepository(db_session).create(
        tenant,
        customer_a.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
    )
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/customers/{customer_b.customer_id}/addresses/{address.address_id}",
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 404


async def test_delete_address_referenced_by_order_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    address = await AddressRepository(db_session).create(
        tenant,
        customer.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
    )
    await db_session.commit()
    await _seed_order_referencing_address(db_session, tenant, customer, address.address_id)

    response = await client.delete(
        f"/api/v1/customers/{customer.customer_id}/addresses/{address.address_id}",
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 409

    get_response = await client.get(
        f"/api/v1/customers/{customer.customer_id}", headers=_auth_headers(tokens)
    )
    assert len(get_response.json()["addresses"]) == 1


async def test_customer_crud_isolated_between_merchants(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens_a = await _register(client, owner_contact="crud-a@example.com")
    tenant_a = await _tenant_for(client, tokens_a)
    tokens_b = await _register(client, owner_contact="crud-b@example.com")
    customer_a = await CustomerRepository(db_session).find_or_create(tenant_a, "+919876543210")
    await db_session.commit()

    update_response = await client.patch(
        f"/api/v1/customers/{customer_a.customer_id}",
        json={"display_name": "Hijacked"},
        headers=_auth_headers(tokens_b),
    )
    assert update_response.status_code == 404
