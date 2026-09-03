import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import ItemRepository
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from notifications.adapters.repository import NotificationTemplateRepository
from notifications.adapters.whatsapp_channel import WhatsAppNotificationChannel
from notifications.domain.rendering import render_template
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from orders.adapters.repository import OrderItemInput, OrderRepository
from shared.encryption import encrypt
from shared.tenant import TenantContext

# --- rendering ---------------------------------------------------------------


def test_render_template_substitutes_known_variables() -> None:
    body = "Hi {{customer_name}}, your order at {{business_name}} is confirmed!"
    context = {"customer_name": "Asha", "business_name": "Test Business"}

    result = render_template(body, context)

    assert result == "Hi Asha, your order at Test Business is confirmed!"


def test_render_template_leaves_unknown_variables_untouched() -> None:
    body = "Order {{order_id}} is {{unknown_field}}."

    result = render_template(body, {"order_id": "abc123"})

    assert result == "Order abc123 is {{unknown_field}}."


def test_render_template_handles_no_variables() -> None:
    body = "Thanks for ordering!"

    assert render_template(body, {}) == "Thanks for ordering!"


# --- WhatsAppNotificationChannel: template vs. default fallback -------------


class FakeSender:
    def __init__(self, *, succeed: bool = True) -> None:
        self.succeed = succeed
        self.calls: list[dict] = []

    async def send_text(
        self, *, phone_number_id: str, access_token: str, to: str, body: str
    ) -> bool:
        self.calls.append({"to": to, "body": body})
        return self.succeed

    async def send_buttons(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        body: str,
        buttons: list[tuple[str, str]],
    ) -> bool:
        raise NotImplementedError


async def _seed_order(db_session: AsyncSession):
    merchant = await MerchantRepository(db_session).create(
        business_name="Test Business", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    await WhatsAppBusinessAccountRepository(db_session).upsert(
        tenant, phone_number_id="PNID1", access_token_encrypted=encrypt("dummy-token")
    )
    customer = await CustomerRepository(db_session).find_or_create(
        tenant, "919876543210", display_name="Asha"
    )
    item = await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    order = await OrderRepository(db_session).create(
        tenant,
        customer_id=customer.customer_id,
        order_type="pickup",
        payment_method="cod",
        payment_status="pending",
        fulfillment_status="new",
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
    return tenant, order


async def test_notify_uses_default_message_when_no_template_configured(
    db_session: AsyncSession,
) -> None:
    tenant, order = await _seed_order(db_session)
    sender = FakeSender()
    channel = WhatsAppNotificationChannel(sender)

    await channel.notify_order_confirmed(merchant_id=tenant.merchant_id, order_id=order.order_id)

    assert "confirmed" in sender.calls[0]["body"].lower()


async def test_notify_uses_active_template_when_configured(db_session: AsyncSession) -> None:
    tenant, order = await _seed_order(db_session)
    await NotificationTemplateRepository(db_session).upsert(
        tenant,
        "order_confirmed",
        template_name="order_confirmed_v1",
        language_code="en",
        body="Hi {{customer_name}}, {{business_name}} received your order {{order_id}}!",
        is_active=True,
    )
    await db_session.commit()
    sender = FakeSender()
    channel = WhatsAppNotificationChannel(sender)

    await channel.notify_order_confirmed(merchant_id=tenant.merchant_id, order_id=order.order_id)

    body = sender.calls[0]["body"]
    assert body == f"Hi Asha, Test Business received your order {order.order_id}!"


async def test_notify_falls_back_to_default_when_template_inactive(
    db_session: AsyncSession,
) -> None:
    tenant, order = await _seed_order(db_session)
    await NotificationTemplateRepository(db_session).upsert(
        tenant,
        "order_confirmed",
        template_name="order_confirmed_v1",
        language_code="en",
        body="This should not be sent.",
        is_active=False,
    )
    await db_session.commit()
    sender = FakeSender()
    channel = WhatsAppNotificationChannel(sender)

    await channel.notify_order_confirmed(merchant_id=tenant.merchant_id, order_id=order.order_id)

    assert "confirmed" in sender.calls[0]["body"].lower()
    assert sender.calls[0]["body"] != "This should not be sent."


async def test_template_only_applies_to_its_own_kind(db_session: AsyncSession) -> None:
    tenant, order = await _seed_order(db_session)
    await NotificationTemplateRepository(db_session).upsert(
        tenant,
        "order_ready",
        template_name="ready_v1",
        language_code="en",
        body="Custom ready message!",
        is_active=True,
    )
    await db_session.commit()
    sender = FakeSender()
    channel = WhatsAppNotificationChannel(sender)

    await channel.notify_order_confirmed(merchant_id=tenant.merchant_id, order_id=order.order_id)

    assert "confirmed" in sender.calls[0]["body"].lower()


# --- API endpoints -------------------------------------------------------------


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


async def test_list_templates_defaults_to_unconfigured(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.get("/api/v1/notifications/templates", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert {t["notification_kind"] for t in body} == {
        "order_confirmed",
        "order_processing",
        "order_ready",
        "order_completed",
        "appointment_requested",
        "appointment_confirmed",
        "appointment_cancelled",
        "appointment_reminder_60m",
        "appointment_reminder_30m",
    }
    assert all(t["is_configured"] is False for t in body)
    assert all(t["is_active"] is False for t in body)


async def test_update_template_persists_and_is_readable(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.put(
        "/api/v1/notifications/templates/order_ready",
        json={
            "template_name": "order_ready_v1",
            "language_code": "en",
            "body": "Hey {{customer_name}}, order's ready!",
            "is_active": True,
        },
        headers=_auth_headers(tokens),
    )
    assert response.status_code == 200
    assert response.json()["is_configured"] is True

    list_response = await client.get(
        "/api/v1/notifications/templates", headers=_auth_headers(tokens)
    )
    ready_template = next(
        t for t in list_response.json() if t["notification_kind"] == "order_ready"
    )
    assert ready_template["body"] == "Hey {{customer_name}}, order's ready!"
    assert ready_template["is_active"] is True


async def test_update_template_with_unknown_kind_returns_404(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.put(
        "/api/v1/notifications/templates/not_a_real_kind",
        json={"template_name": "x", "body": "y", "is_active": True},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 404


async def test_templates_isolated_between_merchants(client: AsyncClient) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    await client.put(
        "/api/v1/notifications/templates/order_confirmed",
        json={"template_name": "a", "body": "Merchant A's message", "is_active": True},
        headers=_auth_headers(tokens_a),
    )
    tokens_b = await _register(client, owner_contact="owner-b@example.com")

    response = await client.get(
        "/api/v1/notifications/templates", headers=_auth_headers(tokens_b)
    )

    confirmed = next(t for t in response.json() if t["notification_kind"] == "order_confirmed")
    assert confirmed["is_configured"] is False
