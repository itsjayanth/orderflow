import datetime
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import shared.scheduler as scheduler_module
from campaigns.adapters.repository import (
    CampaignRecipientRepository,
    CampaignRepository,
    MessageTemplateRepository,
)
from campaigns.domain.audience import (
    InvalidAudienceFilterError,
    resolve_audience,
    validate_audience_filter,
)
from campaigns.domain.campaign_service import create_campaign
from campaigns.domain.tier_enforcement import remaining_quota_today
from catalog.adapters.repository import ItemRepository
from customers.adapters.repository import CustomerRepository
from identity.adapters.repository import MerchantRepository
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from orders.adapters.repository import OrderItemInput, OrderRepository
from shared.encryption import encrypt
from shared.scheduler import send_due_campaigns
from shared.security import decode_token
from shared.tenant import TenantContext


async def _make_tenant(db_session: AsyncSession) -> TenantContext:
    merchant = await MerchantRepository(db_session).create(
        business_name="Campaign Business", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    return TenantContext(merchant_id=merchant.merchant_id)


async def _seed_customer(
    db_session: AsyncSession,
    tenant: TenantContext,
    *,
    whatsapp_number: str,
    display_name: str | None = None,
) -> uuid.UUID:
    customer = await CustomerRepository(db_session).find_or_create(
        tenant, whatsapp_number, display_name=display_name
    )
    return customer.customer_id


async def _seed_order(
    db_session: AsyncSession,
    tenant: TenantContext,
    customer_id: uuid.UUID,
    *,
    placed_at: datetime.datetime,
):
    item = await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    order = await OrderRepository(db_session).create(
        tenant,
        customer_id=customer_id,
        order_type="pickup",
        payment_method="online",
        payment_status="paid",
        fulfillment_status="new",
        items=[
            OrderItemInput(
                item_id=item.item_id, name_snapshot=item.name, price_snapshot=item.price, quantity=1
            )
        ],
    )
    order.placed_at = placed_at
    await db_session.commit()
    return order


# --- audience.py ---


def test_validate_audience_filter_accepts_all() -> None:
    validate_audience_filter({"kind": "all"})


@pytest.mark.parametrize("kind", ["ordered_within_days", "no_order_within_days"])
def test_validate_audience_filter_requires_positive_days(kind: str) -> None:
    with pytest.raises(InvalidAudienceFilterError):
        validate_audience_filter({"kind": kind, "days": 0})
    with pytest.raises(InvalidAudienceFilterError):
        validate_audience_filter({"kind": kind})


def test_validate_audience_filter_rejects_unknown_kind() -> None:
    with pytest.raises(InvalidAudienceFilterError):
        validate_audience_filter({"kind": "segment_x"})


async def test_resolve_audience_all_returns_every_active_customer(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    await _seed_customer(db_session, tenant, whatsapp_number="919876543210")
    await _seed_customer(db_session, tenant, whatsapp_number="919876543211")

    customers = await resolve_audience(db_session, tenant, {"kind": "all"})

    assert len(customers) == 2


async def test_resolve_audience_ordered_within_days(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    now = datetime.datetime.now(datetime.UTC)
    recent_customer = await _seed_customer(db_session, tenant, whatsapp_number="919876543210")
    await _seed_order(
        db_session, tenant, recent_customer, placed_at=now - datetime.timedelta(days=2)
    )
    old_customer = await _seed_customer(db_session, tenant, whatsapp_number="919876543211")
    await _seed_order(
        db_session, tenant, old_customer, placed_at=now - datetime.timedelta(days=40)
    )
    await _seed_customer(db_session, tenant, whatsapp_number="919876543212")  # never ordered

    customers = await resolve_audience(
        db_session, tenant, {"kind": "ordered_within_days", "days": 7}, now=now
    )

    assert {c.customer_id for c in customers} == {recent_customer}


async def test_resolve_audience_no_order_within_days(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    now = datetime.datetime.now(datetime.UTC)
    recent_customer = await _seed_customer(db_session, tenant, whatsapp_number="919876543210")
    await _seed_order(
        db_session, tenant, recent_customer, placed_at=now - datetime.timedelta(days=2)
    )
    old_customer = await _seed_customer(db_session, tenant, whatsapp_number="919876543211")
    await _seed_order(
        db_session, tenant, old_customer, placed_at=now - datetime.timedelta(days=40)
    )
    never_customer = await _seed_customer(db_session, tenant, whatsapp_number="919876543212")

    customers = await resolve_audience(
        db_session, tenant, {"kind": "no_order_within_days", "days": 30}, now=now
    )

    assert {c.customer_id for c in customers} == {old_customer, never_customer}


# --- tier_enforcement.py ---


class _FakeWaba:
    def __init__(self, messaging_tier_daily_limit: int) -> None:
        self.messaging_tier_daily_limit = messaging_tier_daily_limit


def test_remaining_quota_today() -> None:
    assert remaining_quota_today(_FakeWaba(250), 100) == 150


def test_remaining_quota_today_never_negative() -> None:
    assert remaining_quota_today(_FakeWaba(250), 999) == 0


# --- campaign_service.py ---


async def test_create_campaign_callable_directly_with_system_created_by(
    db_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(db_session)
    template = await MessageTemplateRepository(db_session).create(
        tenant,
        name="promo",
        category="MARKETING",
        language_code="en_US",
        header_type="NONE",
        header_text=None,
        header_media_handle=None,
        body_text="Hi",
        body_variable_count=0,
        footer_text=None,
        buttons=[],
    )
    await db_session.commit()

    campaign = await create_campaign(
        db_session,
        tenant,
        name="Reorder nudge",
        template_id=template.template_id,
        audience_filter={"kind": "all"},
        scheduled_at=None,
        created_by="system:reorder_reminder",
    )
    await db_session.commit()

    assert campaign.created_by == "system:reorder_reminder"
    assert campaign.status == "draft"


# --- send_orchestrator.py / shared/scheduler.py: send_due_campaigns ---


class FakeCampaignSender:
    """Only implements send_template_message -- send_campaign_batch never
    calls any other WhatsAppSender method."""

    def __init__(self, *, succeed: bool = True) -> None:
        self.succeed = succeed
        self.calls: list[dict] = []

    async def send_template_message(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        template_name: str,
        language_code: str,
        body_params: list[str],
    ) -> bool:
        self.calls.append({"to": to, "template_name": template_name, "body_params": body_params})
        return self.succeed


async def _seed_campaign_ready_merchant(
    db_session: AsyncSession, *, messaging_tier_daily_limit: int = 250
):
    merchant = await MerchantRepository(db_session).create(
        business_name="Campaign Business", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    waba = await WhatsAppBusinessAccountRepository(db_session).upsert(
        tenant, phone_number_id="PNID1", access_token_encrypted=encrypt("dummy-token")
    )
    waba.messaging_tier_daily_limit = messaging_tier_daily_limit
    await db_session.commit()

    template = await MessageTemplateRepository(db_session).create(
        tenant,
        name="promo",
        category="MARKETING",
        language_code="en_US",
        header_type="NONE",
        header_text=None,
        header_media_handle=None,
        body_text="Hi {{1}}, enjoy a treat from {{2}}!",
        body_variable_count=2,
        footer_text=None,
        buttons=[],
    )
    await MessageTemplateRepository(db_session).set_meta_submission_result(
        template, meta_template_id="META1", status="approved"
    )
    await db_session.commit()
    return merchant, tenant, template


async def test_send_due_campaigns_respects_tier_ceiling_and_resumes_next_day(
    db_session: AsyncSession, monkeypatch
) -> None:
    merchant, tenant, template = await _seed_campaign_ready_merchant(
        db_session, messaging_tier_daily_limit=2
    )
    for i in range(5):
        await _seed_customer(db_session, tenant, whatsapp_number=f"91987654321{i}")

    campaign = await create_campaign(
        db_session,
        tenant,
        name="Weekend promo",
        template_id=template.template_id,
        audience_filter={"kind": "all"},
        scheduled_at=None,
        created_by="staff-1",
    )
    await CampaignRepository(db_session).set_status(campaign, "scheduled")
    await db_session.commit()

    fake = FakeCampaignSender()
    monkeypatch.setattr(scheduler_module, "get_whatsapp_sender", lambda: fake)

    day1 = datetime.datetime.now(datetime.UTC)
    await send_due_campaigns(day1)

    assert len(fake.calls) == 2
    counts = await CampaignRecipientRepository(db_session).counts_by_status(campaign.campaign_id)
    assert counts.get("sent") == 2
    assert counts.get("pending") == 3
    # send_due_campaigns runs in its own SessionFactory() sessions, distinct
    # from db_session -- db_session.refresh() is required to see their
    # committed writes on `campaign` rather than db_session's own stale
    # identity-mapped copy (same convention test_scheduler.py's
    # stale_order.placed_at test already uses).
    await db_session.refresh(campaign)
    assert campaign.status == "sending"  # not completed -- overflow remains

    # A same-day second tick sends nothing more -- the tier is exhausted
    # for today.
    await send_due_campaigns(day1)
    assert len(fake.calls) == 2

    # Simulated day boundary: the tier resets to 2/day again (not an
    # unlimited catch-up), so day2's tick sends 2 more (4 total), leaving
    # 1 still pending and the campaign still "sending".
    day2 = day1 + datetime.timedelta(days=1)
    await send_due_campaigns(day2)

    assert len(fake.calls) == 4
    counts = await CampaignRecipientRepository(db_session).counts_by_status(campaign.campaign_id)
    assert counts.get("sent") == 4
    assert counts.get("pending") == 1
    await db_session.refresh(campaign)
    assert campaign.status == "sending"

    # Day 3: the last recipient sends, and the campaign reaches completed.
    day3 = day2 + datetime.timedelta(days=1)
    await send_due_campaigns(day3)

    assert len(fake.calls) == 5
    counts = await CampaignRecipientRepository(db_session).counts_by_status(campaign.campaign_id)
    assert counts.get("sent") == 5
    assert "pending" not in counts
    await db_session.refresh(campaign)
    assert campaign.status == "completed"
    assert campaign.completed_at is not None

    # Body params carried customer name (blank -- none of these customers
    # set a display_name) and the merchant's business name.
    assert fake.calls[0]["body_params"][1] == merchant.business_name


async def test_send_due_campaigns_skips_opted_out_customer(
    db_session: AsyncSession, monkeypatch
) -> None:
    _, tenant, template = await _seed_campaign_ready_merchant(db_session)
    opted_out_id = await _seed_customer(db_session, tenant, whatsapp_number="919876543210")
    customer = await CustomerRepository(db_session).get(tenant, opted_out_id)
    assert customer is not None
    await CustomerRepository(db_session).set_marketing_opt_out(customer, opted_out=True)
    await _seed_customer(db_session, tenant, whatsapp_number="919876543211")
    await db_session.commit()

    campaign = await create_campaign(
        db_session,
        tenant,
        name="Promo",
        template_id=template.template_id,
        audience_filter={"kind": "all"},
        scheduled_at=None,
        created_by="staff-1",
    )
    await CampaignRepository(db_session).set_status(campaign, "scheduled")
    await db_session.commit()

    fake = FakeCampaignSender()
    monkeypatch.setattr(scheduler_module, "get_whatsapp_sender", lambda: fake)

    await send_due_campaigns()

    assert len(fake.calls) == 1
    counts = await CampaignRecipientRepository(db_session).counts_by_status(campaign.campaign_id)
    assert counts.get("skipped_opted_out") == 1
    assert counts.get("sent") == 1


async def test_send_due_campaigns_ignores_draft_campaigns(
    db_session: AsyncSession, monkeypatch
) -> None:
    _, tenant, template = await _seed_campaign_ready_merchant(db_session)
    await _seed_customer(db_session, tenant, whatsapp_number="919876543210")

    await create_campaign(
        db_session,
        tenant,
        name="Still a draft",
        template_id=template.template_id,
        audience_filter={"kind": "all"},
        scheduled_at=None,
        created_by="staff-1",
    )
    await db_session.commit()

    fake = FakeCampaignSender()
    monkeypatch.setattr(scheduler_module, "get_whatsapp_sender", lambda: fake)

    await send_due_campaigns()

    assert fake.calls == []


# --- API: create -> schedule (gated on approval) -> cancel ---


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


async def test_schedule_campaign_requires_approved_template(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    payload = decode_token(tokens["access_token"], expected_type="access")
    tenant = TenantContext(merchant_id=uuid.UUID(payload["merchant_id"]))

    await WhatsAppBusinessAccountRepository(db_session).upsert(
        tenant, phone_number_id="PNID1", access_token_encrypted=encrypt("dummy-token")
    )
    template = await MessageTemplateRepository(db_session).create(
        tenant,
        name="promo",
        category="MARKETING",
        language_code="en_US",
        header_type="NONE",
        header_text=None,
        header_media_handle=None,
        body_text="Hi",
        body_variable_count=0,
        footer_text=None,
        buttons=[],
    )
    await MessageTemplateRepository(db_session).set_meta_submission_result(
        template, meta_template_id="META1", status="pending"
    )
    await db_session.commit()

    create_response = await client.post(
        "/api/v1/campaigns",
        json={"name": "Promo", "template_id": str(template.template_id)},
        headers=_auth_headers(tokens),
    )
    assert create_response.status_code == 201, create_response.text
    campaign_id = create_response.json()["campaign_id"]

    schedule_response = await client.post(
        f"/api/v1/campaigns/{campaign_id}/schedule", headers=_auth_headers(tokens)
    )
    assert schedule_response.status_code == 422

    await MessageTemplateRepository(db_session).update_approval_status(
        "META1", status="approved", reason=None
    )
    await db_session.commit()

    schedule_response = await client.post(
        f"/api/v1/campaigns/{campaign_id}/schedule", headers=_auth_headers(tokens)
    )
    assert schedule_response.status_code == 200, schedule_response.text
    assert schedule_response.json()["status"] == "scheduled"

    detail_response = await client.get(
        f"/api/v1/campaigns/{campaign_id}", headers=_auth_headers(tokens)
    )
    assert detail_response.json()["recipient_counts"] == {
        "pending": 0,
        "sent": 0,
        "failed": 0,
        "skipped_opted_out": 0,
        "skipped_no_number": 0,
    }


async def test_cancel_campaign_leaves_sent_rows_intact(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    tokens = await _register(client)
    payload = decode_token(tokens["access_token"], expected_type="access")
    tenant = TenantContext(merchant_id=uuid.UUID(payload["merchant_id"]))

    waba = await WhatsAppBusinessAccountRepository(db_session).upsert(
        tenant, phone_number_id="PNID1", access_token_encrypted=encrypt("dummy-token")
    )
    waba.messaging_tier_daily_limit = 1
    await _seed_customer(db_session, tenant, whatsapp_number="919876543210")
    await _seed_customer(db_session, tenant, whatsapp_number="919876543211")
    template = await MessageTemplateRepository(db_session).create(
        tenant,
        name="promo",
        category="MARKETING",
        language_code="en_US",
        header_type="NONE",
        header_text=None,
        header_media_handle=None,
        body_text="Hi",
        body_variable_count=0,
        footer_text=None,
        buttons=[],
    )
    await MessageTemplateRepository(db_session).set_meta_submission_result(
        template, meta_template_id="META1", status="approved"
    )
    await db_session.commit()

    create_response = await client.post(
        "/api/v1/campaigns",
        json={"name": "Promo", "template_id": str(template.template_id)},
        headers=_auth_headers(tokens),
    )
    campaign_id = create_response.json()["campaign_id"]
    await client.post(f"/api/v1/campaigns/{campaign_id}/schedule", headers=_auth_headers(tokens))

    fake = FakeCampaignSender()
    monkeypatch.setattr(scheduler_module, "get_whatsapp_sender", lambda: fake)
    await send_due_campaigns()
    assert len(fake.calls) == 1

    cancel_response = await client.post(
        f"/api/v1/campaigns/{campaign_id}/cancel", headers=_auth_headers(tokens)
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "failed"

    # A cancelled campaign is no longer "scheduled"/"sending" -- the next
    # tick doesn't pick it up, so the still-pending recipient is never sent.
    await send_due_campaigns(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
    assert len(fake.calls) == 1

    detail_response = await client.get(
        f"/api/v1/campaigns/{campaign_id}", headers=_auth_headers(tokens)
    )
    counts = detail_response.json()["recipient_counts"]
    assert counts["sent"] == 1
    assert counts["pending"] == 1
