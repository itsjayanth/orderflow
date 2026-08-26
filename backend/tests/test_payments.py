import hashlib
import hmac
import json
import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import ItemRepository
from customers.adapters.repository import CustomerRepository
from orders.adapters.repository import OrderRepository
from shared.tenant import TenantContext


async def _register(client: AsyncClient, owner_contact: str = "owner@example.com") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "business_name": "Test Kitchen",
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


async def _seed_customer_and_item(db_session: AsyncSession, tenant: TenantContext) -> tuple:
    customer = await CustomerRepository(db_session).find_or_create(tenant, "+919876543210")
    item = await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    await db_session.commit()
    return customer, item


# --- payment settings ------------------------------------------------------


async def test_get_payment_settings_defaults_to_dummy(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.get("/api/v1/payments/settings", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert body["razorpay_key_id"] is None
    assert body["razorpay_key_secret_set"] is False
    assert body["using_real_gateway"] is False


async def test_update_payment_settings_with_real_looking_key(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.put(
        "/api/v1/payments/settings",
        json={"razorpay_key_id": "rzp_test_abc123", "razorpay_key_secret": "shhh"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["razorpay_key_id"] == "rzp_test_abc123"
    assert body["razorpay_key_secret_set"] is True
    assert body["using_real_gateway"] is True
    assert "shhh" not in response.text


async def test_update_payment_settings_with_placeholder_key_stays_dummy(
    client: AsyncClient,
) -> None:
    tokens = await _register(client)

    response = await client.put(
        "/api/v1/payments/settings",
        json={"razorpay_key_id": "not-a-real-key", "razorpay_key_secret": "shhh"},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200
    assert response.json()["using_real_gateway"] is False


# --- test-checkout -----------------------------------------------------


async def test_checkout_online_creates_awaiting_payment_order_with_link(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    _, item = await _seed_customer_and_item(db_session, tenant)

    response = await client.post(
        "/api/v1/payments/test-checkout",
        json={
            "customer_whatsapp_number": "+919876543210",
            "customer_display_name": "Asha",
            "items": [{"item_id": str(item.item_id), "quantity": 2}],
            "payment_method": "online",
        },
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["payment_status"] == "awaiting_payment"
    assert body["fulfillment_status"] is None
    assert body["total"] == "698.00"
    assert body["payment_link_url"].startswith("https://dummy-checkout.orderflow.local/pay/")


async def test_checkout_reuses_existing_customer_by_phone_number(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer, item = await _seed_customer_and_item(db_session, tenant)

    response = await client.post(
        "/api/v1/payments/test-checkout",
        json={
            "customer_whatsapp_number": "+919876543210",
            "items": [{"item_id": str(item.item_id), "quantity": 1}],
            "payment_method": "cod",
        },
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 201, response.text
    customers = await client.get("/api/v1/customers", headers=_auth_headers(tokens))
    assert len(customers.json()) == 1
    assert customers.json()[0]["customer_id"] == str(customer.customer_id)


async def test_checkout_cod_creates_new_order_immediately(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    _, item = await _seed_customer_and_item(db_session, tenant)

    response = await client.post(
        "/api/v1/payments/test-checkout",
        json={
            "customer_whatsapp_number": "+919876543210",
            "items": [{"item_id": str(item.item_id), "quantity": 1}],
            "payment_method": "cod",
        },
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["payment_status"] == "cod_pending"
    assert body["fulfillment_status"] == "new"
    assert body["payment_link_url"] is None


async def test_checkout_unknown_menu_item_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await _seed_customer_and_item(db_session, tenant)

    response = await client.post(
        "/api/v1/payments/test-checkout",
        json={
            "customer_whatsapp_number": "+919876543210",
            "items": [{"item_id": str(uuid.uuid4()), "quantity": 1}],
        },
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 404


async def test_checkout_menu_item_from_another_merchant_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    tenant_a = await _tenant_for(client, tokens_a)
    await _seed_customer_and_item(db_session, tenant_a)

    tokens_b = await _register(client, owner_contact="owner-b@example.com")
    tenant_b = await _tenant_for(client, tokens_b)
    _, item_b = await _seed_customer_and_item(db_session, tenant_b)

    response = await client.post(
        "/api/v1/payments/test-checkout",
        json={
            "customer_whatsapp_number": "+919876543210",
            "items": [{"item_id": str(item_b.item_id), "quantity": 1}],
        },
        headers=_auth_headers(tokens_a),
    )

    assert response.status_code == 404


# --- webhook: full dummy-gateway payment lifecycle --------------------------


def _sign(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _webhook_payload(*, event: str, payment_id: str, order_id: str) -> bytes:
    return json.dumps(
        {
            "event": event,
            "payload": {"payment": {"entity": {"id": payment_id, "order_id": order_id}}},
        }
    ).encode("utf-8")


async def test_webhook_marks_order_paid_and_gates_fulfillment(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer, item = await _seed_customer_and_item(db_session, tenant)

    checkout = await client.post(
        "/api/v1/payments/test-checkout",
        json={
            "customer_whatsapp_number": "+919876543210",
            "items": [{"item_id": str(item.item_id), "quantity": 1}],
            "payment_method": "online",
        },
        headers=_auth_headers(tokens),
    )
    order_id = checkout.json()["order_id"]
    provider_order_id = checkout.json()["payment_link_url"].split("/pay/")[1].split("?")[0]

    # The dummy secret used when no real credentials are configured, per
    # gateway_selector.resolve_credentials.
    secret = f"dummy-secret-{tenant.merchant_id}"
    payload = _webhook_payload(
        event="payment.captured", payment_id="pay_abc123", order_id=provider_order_id
    )
    signature = _sign(payload, secret)

    response = await client.post(
        f"/api/v1/payments/webhook/razorpay/{tenant.merchant_id}",
        content=payload,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    order_response = await client.get(f"/api/v1/orders/{order_id}", headers=_auth_headers(tokens))
    assert order_response.status_code == 200
    order_body = order_response.json()
    assert order_body["payment_status"] == "paid"
    assert order_body["fulfillment_status"] == "new"
    assert order_body["paid_at"] is not None


async def test_webhook_payment_failed_does_not_gate_fulfillment(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer, item = await _seed_customer_and_item(db_session, tenant)

    checkout = await client.post(
        "/api/v1/payments/test-checkout",
        json={
            "customer_whatsapp_number": "+919876543210",
            "items": [{"item_id": str(item.item_id), "quantity": 1}],
            "payment_method": "online",
        },
        headers=_auth_headers(tokens),
    )
    order_id = checkout.json()["order_id"]
    provider_order_id = checkout.json()["payment_link_url"].split("/pay/")[1].split("?")[0]

    secret = f"dummy-secret-{tenant.merchant_id}"
    payload = _webhook_payload(
        event="payment.failed", payment_id="pay_fail1", order_id=provider_order_id
    )
    signature = _sign(payload, secret)

    response = await client.post(
        f"/api/v1/payments/webhook/razorpay/{tenant.merchant_id}",
        content=payload,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200

    order_response = await client.get(f"/api/v1/orders/{order_id}", headers=_auth_headers(tokens))
    body = order_response.json()
    assert body["payment_status"] == "payment_failed"
    assert body["fulfillment_status"] is None


async def test_webhook_rejects_invalid_signature(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer, item = await _seed_customer_and_item(db_session, tenant)

    checkout = await client.post(
        "/api/v1/payments/test-checkout",
        json={
            "customer_whatsapp_number": "+919876543210",
            "items": [{"item_id": str(item.item_id), "quantity": 1}],
            "payment_method": "online",
        },
        headers=_auth_headers(tokens),
    )
    provider_order_id = checkout.json()["payment_link_url"].split("/pay/")[1].split("?")[0]

    payload = _webhook_payload(
        event="payment.captured", payment_id="pay_x", order_id=provider_order_id
    )
    bad_signature = _sign(payload, "totally-wrong-secret")

    response = await client.post(
        f"/api/v1/payments/webhook/razorpay/{tenant.merchant_id}",
        content=payload,
        headers={"X-Razorpay-Signature": bad_signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 400


async def test_webhook_redelivery_is_idempotent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    customer, item = await _seed_customer_and_item(db_session, tenant)

    checkout = await client.post(
        "/api/v1/payments/test-checkout",
        json={
            "customer_whatsapp_number": "+919876543210",
            "items": [{"item_id": str(item.item_id), "quantity": 1}],
            "payment_method": "online",
        },
        headers=_auth_headers(tokens),
    )
    order_id = checkout.json()["order_id"]
    provider_order_id = checkout.json()["payment_link_url"].split("/pay/")[1].split("?")[0]

    secret = f"dummy-secret-{tenant.merchant_id}"
    payload = _webhook_payload(
        event="payment.captured", payment_id="pay_dup1", order_id=provider_order_id
    )
    signature = _sign(payload, secret)

    first = await client.post(
        f"/api/v1/payments/webhook/razorpay/{tenant.merchant_id}",
        content=payload,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    second = await client.post(
        f"/api/v1/payments/webhook/razorpay/{tenant.merchant_id}",
        content=payload,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )

    assert first.json()["status"] == "ok"
    assert second.json()["status"] == "duplicate"

    order_response = await client.get(f"/api/v1/orders/{order_id}", headers=_auth_headers(tokens))
    assert order_response.json()["payment_status"] == "paid"


async def test_webhook_unknown_order_returns_404(client: AsyncClient) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)

    secret = f"dummy-secret-{tenant.merchant_id}"
    payload = _webhook_payload(
        event="payment.captured", payment_id="pay_orphan", order_id="dummy_order_doesnotexist"
    )
    signature = _sign(payload, secret)

    response = await client.post(
        f"/api/v1/payments/webhook/razorpay/{tenant.merchant_id}",
        content=payload,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 404


async def test_order_repository_finds_stale_awaiting_payment_orders(
    db_session: AsyncSession,
) -> None:
    import datetime

    from identity.adapters.repository import MerchantRepository
    from orders.adapters.repository import OrderItemInput

    merchant = await MerchantRepository(db_session).create(
        business_name="Stale Kitchen", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    customer, item = await _seed_customer_and_item(db_session, tenant)

    order = await OrderRepository(db_session).create(
        tenant,
        customer_id=customer.customer_id,
        order_type="pickup",
        payment_method="online",
        payment_status="awaiting_payment",
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

    future_threshold = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=1)
    past_threshold = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=1)

    stale = await OrderRepository(db_session).list_stale_awaiting_payment(future_threshold)
    not_yet_stale = await OrderRepository(db_session).list_stale_awaiting_payment(past_threshold)

    assert order.order_id in {o.order_id for o in stale}
    assert order.order_id not in {o.order_id for o in not_yet_stale}
