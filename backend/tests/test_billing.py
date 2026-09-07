import hashlib
import hmac
import json
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from billing.adapters.repository import PlanRepository, SubscriptionRepository
from shared.config import get_settings
from shared.tenant import TenantContext


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


def _sign(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _webhook_payload(
    *, event: str, subscription_id: str, payment_id: str | None = None
) -> bytes:
    body = {
        "event": event,
        "payload": {"subscription": {"entity": {"id": subscription_id}}},
    }
    if payment_id is not None:
        body["payload"]["payment"] = {"entity": {"id": payment_id}}
    return json.dumps(body).encode("utf-8")


# --- registration wires up a trialing Growth subscription --------------------


async def test_register_creates_trialing_growth_subscription(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)

    subscription = await SubscriptionRepository(db_session).get(tenant)
    assert subscription is not None
    assert subscription.status == "trialing"
    assert subscription.trial_ends_at is not None

    plan = await PlanRepository(db_session).get(subscription.plan_id)
    assert plan is not None
    assert plan.tier == "growth"
    assert plan.billing_interval == "monthly"


# --- GET /billing/plans (public) ---------------------------------------------


async def test_list_plans_is_public_and_returns_six_plans(client: AsyncClient) -> None:
    response = await client.get("/api/v1/billing/plans")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 6
    tiers_and_intervals = {(p["tier"], p["billing_interval"]) for p in body}
    assert tiers_and_intervals == {
        ("starter", "monthly"),
        ("starter", "annual"),
        ("growth", "monthly"),
        ("growth", "annual"),
        ("pro", "monthly"),
        ("pro", "annual"),
    }
    assert all("razorpay_plan_id" not in p for p in body)


# --- GET /billing/subscription ------------------------------------------------


async def test_get_subscription_returns_trial_state(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.get("/api/v1/billing/subscription", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "trialing"
    assert body["plan"]["tier"] == "growth"
    assert body["orders_used_this_cycle"] == 0
    assert body["order_cap"] == 750


async def test_get_subscription_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/billing/subscription")
    assert response.status_code == 401


# --- POST /billing/subscribe --------------------------------------------------


async def test_subscribe_creates_provider_subscription_id(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    plans = (await client.get("/api/v1/billing/plans")).json()
    pro_plan = next(p for p in plans if p["tier"] == "pro" and p["billing_interval"] == "monthly")

    response = await client.post(
        "/api/v1/billing/subscribe",
        json={"plan_id": pro_plan["plan_id"]},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider_subscription_id"].startswith("dummy_sub_")
    assert body["checkout_url"].startswith("https://dummy-billing.orderflow.local/activate/")

    subscription = await SubscriptionRepository(db_session).get(tenant)
    assert subscription is not None
    assert subscription.provider_subscription_id == body["provider_subscription_id"]
    # subscribe never flips status itself -- only the webhook does, once
    # payment/mandate actually confirms.
    assert subscription.status == "trialing"


async def test_subscribe_unknown_plan_returns_404(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.post(
        "/api/v1/billing/subscribe",
        json={"plan_id": str(uuid.uuid4())},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 404


# --- POST /billing/change-plan ------------------------------------------------


async def test_change_plan_updates_plan_id(client: AsyncClient) -> None:
    tokens = await _register(client)
    plans = (await client.get("/api/v1/billing/plans")).json()
    starter_plan = next(
        p for p in plans if p["tier"] == "starter" and p["billing_interval"] == "monthly"
    )

    response = await client.post(
        "/api/v1/billing/change-plan",
        json={"plan_id": starter_plan["plan_id"]},
        headers=_auth_headers(tokens),
    )

    assert response.status_code == 200, response.text
    assert response.json()["plan"]["tier"] == "starter"


async def test_change_plan_without_existing_subscription_returns_409_or_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A Subscription always exists post-registration in this codebase
    (created in the same transaction), so this exercises the defensive
    404 path directly against the repository layer rather than needing a
    subscription-less merchant to exist through the API."""
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    subscription = await SubscriptionRepository(db_session).get(tenant)
    assert subscription is not None
    await db_session.delete(subscription)
    await db_session.commit()

    plans = (await client.get("/api/v1/billing/plans")).json()
    starter_plan = next(
        p for p in plans if p["tier"] == "starter" and p["billing_interval"] == "monthly"
    )

    response = await client.post(
        "/api/v1/billing/change-plan",
        json={"plan_id": starter_plan["plan_id"]},
        headers=_auth_headers(tokens),
    )

    assert response.status_code in (404, 409)


# --- POST /billing/cancel -----------------------------------------------------


async def test_cancel_sets_cancel_at_period_end_without_changing_status(
    client: AsyncClient,
) -> None:
    tokens = await _register(client)

    response = await client.post("/api/v1/billing/cancel", headers=_auth_headers(tokens))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cancel_at_period_end"] is True
    assert body["status"] == "trialing"


# --- tenant isolation ---------------------------------------------------------


async def test_merchant_cannot_read_another_merchants_subscription(
    client: AsyncClient,
) -> None:
    tokens_a = await _register(client, owner_contact="owner-a@example.com")
    tokens_b = await _register(client, owner_contact="owner-b@example.com")

    # Each merchant only ever sees their own subscription via CurrentTenant
    # resolution from their own JWT -- there's no endpoint that accepts a
    # foreign merchant_id at all, so cross-tenant access is exercised here
    # by confirming B's token yields B's own (distinct) subscription data,
    # never A's.
    response_a = await client.get("/api/v1/billing/subscription", headers=_auth_headers(tokens_a))
    response_b = await client.get("/api/v1/billing/subscription", headers=_auth_headers(tokens_b))

    assert response_a.json()["merchant_id"] != response_b.json()["merchant_id"]


async def test_get_by_provider_subscription_id_is_not_tenant_scoped_but_resolves_correctly(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The webhook path resolves tenant identity purely from
    provider_subscription_id -- confirm merchant A's dummy checkout id
    only ever resolves to merchant A's subscription, never merchant B's,
    even though the lookup method itself takes no TenantContext."""
    tokens_a = await _register(client, owner_contact="owner-a2@example.com")
    tokens_b = await _register(client, owner_contact="owner-b2@example.com")
    tenant_a = await _tenant_for(client, tokens_a)
    tenant_b = await _tenant_for(client, tokens_b)

    plans = (await client.get("/api/v1/billing/plans")).json()
    plan_id = plans[0]["plan_id"]

    checkout_a = await client.post(
        "/api/v1/billing/subscribe", json={"plan_id": plan_id}, headers=_auth_headers(tokens_a)
    )
    provider_subscription_id_a = checkout_a.json()["provider_subscription_id"]

    resolved = await SubscriptionRepository(db_session).get_by_provider_subscription_id(
        provider_subscription_id_a
    )
    assert resolved is not None
    assert resolved.merchant_id == tenant_a.merchant_id
    assert resolved.merchant_id != tenant_b.merchant_id


# --- webhook: happy path, bad signature, idempotency, unknown subscription ---


async def test_webhook_activates_trialing_subscription(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    plans = (await client.get("/api/v1/billing/plans")).json()
    subscribe = await client.post(
        "/api/v1/billing/subscribe",
        json={"plan_id": plans[0]["plan_id"]},
        headers=_auth_headers(tokens),
    )
    provider_subscription_id = subscribe.json()["provider_subscription_id"]

    secret = get_settings().platform_razorpay_webhook_secret
    payload = _webhook_payload(
        event="subscription.activated",
        subscription_id=provider_subscription_id,
        payment_id="pay_billing_1",
    )
    signature = _sign(payload, secret)

    response = await client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    subscription = await SubscriptionRepository(db_session).get(tenant)
    assert subscription is not None
    assert subscription.status == "active"


async def test_webhook_rejects_invalid_signature(client: AsyncClient) -> None:
    payload = _webhook_payload(event="subscription.activated", subscription_id="sub_x")
    bad_signature = _sign(payload, "totally-wrong-secret")

    response = await client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"X-Razorpay-Signature": bad_signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 400


async def test_webhook_unknown_subscription_returns_404(client: AsyncClient) -> None:
    secret = get_settings().platform_razorpay_webhook_secret
    payload = _webhook_payload(
        event="subscription.activated",
        subscription_id="dummy_sub_doesnotexist",
        payment_id="pay_orphan",
    )
    signature = _sign(payload, secret)

    response = await client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 404


async def test_webhook_redelivery_is_idempotent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    plans = (await client.get("/api/v1/billing/plans")).json()
    subscribe = await client.post(
        "/api/v1/billing/subscribe",
        json={"plan_id": plans[0]["plan_id"]},
        headers=_auth_headers(tokens),
    )
    provider_subscription_id = subscribe.json()["provider_subscription_id"]

    secret = get_settings().platform_razorpay_webhook_secret
    payload = _webhook_payload(
        event="subscription.activated",
        subscription_id=provider_subscription_id,
        payment_id="pay_dup_1",
    )
    signature = _sign(payload, secret)

    first = await client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    second = await client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )

    assert first.json()["status"] == "ok"
    assert second.json()["status"] == "duplicate"

    subscription = await SubscriptionRepository(db_session).get(tenant)
    assert subscription is not None
    assert subscription.status == "active"


async def test_webhook_redelivery_without_payment_id_caught_by_illegal_transition(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A redelivered webhook with no payment entity at all can't dedupe on
    provider_payment_id -- the second belt-and-suspenders layer (the state
    machine rejecting an already-applied transition) is what catches it."""
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    plans = (await client.get("/api/v1/billing/plans")).json()
    subscribe = await client.post(
        "/api/v1/billing/subscribe",
        json={"plan_id": plans[0]["plan_id"]},
        headers=_auth_headers(tokens),
    )
    provider_subscription_id = subscribe.json()["provider_subscription_id"]

    secret = get_settings().platform_razorpay_webhook_secret
    payload = _webhook_payload(
        event="subscription.activated", subscription_id=provider_subscription_id
    )
    signature = _sign(payload, secret)

    first = await client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    second = await client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )

    assert first.json()["status"] == "ok"
    assert second.json()["status"] == "duplicate"

    subscription = await SubscriptionRepository(db_session).get(tenant)
    assert subscription is not None
    assert subscription.status == "active"
