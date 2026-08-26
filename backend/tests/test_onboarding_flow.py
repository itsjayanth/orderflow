import itertools
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import ItemRepository
from conversation.adapters.whatsapp_client import WhatsAppSender
from conversation.domain.handler import handle_inbound_message
from conversation.domain.webhook_parser import InboundMessage
from identity.adapters.repository import MerchantRepository
from identity.domain.models import ONBOARDING_STATUSES, Merchant
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from onboarding.domain.onboarding_service import (
    advance_after_profile_completed,
    advance_after_whatsapp_connected,
    try_advance_for_catalog_ready,
)
from onboarding.domain.state_machine import (
    ONBOARDING_TRANSITIONS,
    IllegalOnboardingTransitionError,
    transition_onboarding_status,
)
from shared.encryption import encrypt
from shared.tenant import TenantContext

# --- state machine: every legal transition succeeds -------------------------


def _merchant(onboarding_status: str) -> Merchant:
    return Merchant(
        merchant_id=uuid.uuid4(),
        business_name="Test Business",
        owner_contact=f"{uuid.uuid4()}@example.com",
        onboarding_status=onboarding_status,
    )


@pytest.mark.parametrize(("from_status", "to_status"), sorted(ONBOARDING_TRANSITIONS))
def test_legal_onboarding_transition_succeeds(from_status: str, to_status: str) -> None:
    merchant = _merchant(from_status)

    transition_onboarding_status(merchant, to_status)

    assert merchant.onboarding_status == to_status


_ALL_ILLEGAL_ONBOARDING_COMBOS = [
    (from_status, to_status)
    for from_status, to_status in itertools.product(ONBOARDING_STATUSES, ONBOARDING_STATUSES)
    if (from_status, to_status) not in ONBOARDING_TRANSITIONS
]


@pytest.mark.parametrize(("from_status", "to_status"), _ALL_ILLEGAL_ONBOARDING_COMBOS)
def test_illegal_onboarding_transition_raises(from_status: str, to_status: str) -> None:
    merchant = _merchant(from_status)

    with pytest.raises(IllegalOnboardingTransitionError):
        transition_onboarding_status(merchant, to_status)

    # Rejected transitions never mutate state.
    assert merchant.onboarding_status == from_status


def test_step_skipping_is_rejected() -> None:
    merchant = _merchant("registered")

    with pytest.raises(IllegalOnboardingTransitionError):
        transition_onboarding_status(merchant, "profile_completed")


# --- onboarding_service: end-to-end progression through the six states -----


async def _make_tenant(db_session: AsyncSession) -> TenantContext:
    merchant = await MerchantRepository(db_session).create(
        business_name="Test Business", owner_contact=f"{uuid.uuid4()}@example.com"
    )
    await db_session.commit()
    return TenantContext(merchant_id=merchant.merchant_id)


async def test_new_merchant_starts_registered(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)

    merchant = await MerchantRepository(db_session).get(tenant.merchant_id)

    assert merchant is not None
    assert merchant.onboarding_status == "registered"


async def test_connecting_whatsapp_advances_to_whatsapp_verified(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    await WhatsAppBusinessAccountRepository(db_session).upsert(
        tenant, phone_number_id="PNID1", access_token_encrypted=encrypt("dummy-token")
    )

    merchant = await advance_after_whatsapp_connected(db_session, tenant)

    assert merchant.onboarding_status == "whatsapp_verified"


async def test_reconnecting_whatsapp_does_not_move_status_backwards(
    db_session: AsyncSession,
) -> None:
    tenant = await _make_tenant(db_session)
    await advance_after_whatsapp_connected(db_session, tenant)
    merchant = await MerchantRepository(db_session).get(tenant.merchant_id)
    assert merchant is not None
    merchant.business_address_line1 = "1 MG Road"
    merchant = await advance_after_profile_completed(db_session, tenant)
    assert merchant.onboarding_status == "profile_completed"

    # Updating WhatsApp credentials again later must not un-advance status.
    merchant = await advance_after_whatsapp_connected(db_session, tenant)
    assert merchant.onboarding_status == "profile_completed"


async def test_catalog_ready_and_live_cascade_once_gate_is_met(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    await advance_after_whatsapp_connected(db_session, tenant)
    merchant = await MerchantRepository(db_session).get(tenant.merchant_id)
    assert merchant is not None
    merchant.business_address_line1 = "1 MG Road"
    await advance_after_profile_completed(db_session, tenant)

    # Gate not met yet -- no menu items.
    merchant = await try_advance_for_catalog_ready(db_session, tenant)
    assert merchant.onboarding_status == "profile_completed"

    await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )

    merchant = await try_advance_for_catalog_ready(db_session, tenant)
    assert merchant.onboarding_status == "live"


async def test_catalog_ready_gate_ignores_unavailable_items(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    await advance_after_whatsapp_connected(db_session, tenant)
    merchant = await MerchantRepository(db_session).get(tenant.merchant_id)
    assert merchant is not None
    merchant.business_address_line1 = "1 MG Road"
    await advance_after_profile_completed(db_session, tenant)

    item = await ItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    await ItemRepository(db_session).update(tenant, item.item_id, is_available=False)

    merchant = await try_advance_for_catalog_ready(db_session, tenant)

    assert merchant.onboarding_status == "profile_completed"


# --- API endpoints -----------------------------------------------------------


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


async def test_onboarding_status_endpoint_reflects_progress(client: AsyncClient) -> None:
    tokens = await _register(client)

    response = await client.get("/api/v1/onboarding/status", headers=_auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert body["onboarding_status"] == "registered"
    assert body["whatsapp_connected"] is False
    assert body["profile_completed"] is False
    assert body["has_available_item"] is False


async def test_connect_whatsapp_endpoint_advances_status(client: AsyncClient) -> None:
    tokens = await _register(client)

    await client.put(
        "/api/v1/onboarding/whatsapp",
        json={"phone_number_id": "1234567890", "access_token": "dummy-meta-access-token"},
        headers=_auth_headers(tokens),
    )

    response = await client.get("/api/v1/onboarding/status", headers=_auth_headers(tokens))
    assert response.json()["onboarding_status"] == "whatsapp_verified"


async def test_save_profile_endpoint_advances_status(client: AsyncClient) -> None:
    tokens = await _register(client)
    await client.put(
        "/api/v1/onboarding/whatsapp",
        json={"phone_number_id": "1234567890", "access_token": "dummy-meta-access-token"},
        headers=_auth_headers(tokens),
    )

    response = await client.put(
        "/api/v1/onboarding/profile",
        json={
            "address_line1": "1 MG Road",
            "city": "Bangalore",
            "pincode": "560001",
            "business_category": "North Indian",
        },
        headers=_auth_headers(tokens),
    )
    assert response.status_code == 200
    assert response.json()["address_line1"] == "1 MG Road"

    status_response = await client.get("/api/v1/onboarding/status", headers=_auth_headers(tokens))
    assert status_response.json()["onboarding_status"] == "profile_completed"
    assert status_response.json()["profile_completed"] is True


async def test_full_wizard_reaches_live(client: AsyncClient) -> None:
    tokens = await _register(client)
    headers = _auth_headers(tokens)

    await client.put(
        "/api/v1/onboarding/whatsapp",
        json={"phone_number_id": "1234567890", "access_token": "dummy-meta-access-token"},
        headers=headers,
    )
    await client.put(
        "/api/v1/onboarding/profile",
        json={
            "address_line1": "1 MG Road",
            "city": "Bangalore",
            "pincode": "560001",
            "business_category": "North Indian",
        },
        headers=headers,
    )
    create_response = await client.post(
        "/api/v1/catalog/items",
        json={"category": "Mains", "name": "Butter Chicken", "price": "349.00"},
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text

    response = await client.get("/api/v1/onboarding/status", headers=headers)

    assert response.json()["onboarding_status"] == "live"
    assert response.json()["has_available_item"] is True


# --- conversation handler guard ---------------------------------------------


class FakeSender(WhatsAppSender):
    def __init__(self) -> None:
        self.button_calls: list[dict] = []

    async def send_text(
        self, *, phone_number_id: str, access_token: str, to: str, body: str
    ) -> bool:
        return True

    async def send_buttons(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        to: str,
        body: str,
        buttons: list[tuple[str, str]],
    ) -> bool:
        self.button_calls.append({"to": to, "body": body, "buttons": buttons})
        return True


def _inbound(*, phone_number_id: str = "PNID1", from_phone: str = "919876543210") -> InboundMessage:
    return InboundMessage(
        phone_number_id=phone_number_id,
        whatsapp_message_id=f"wamid.{uuid.uuid4().hex}",
        from_phone=from_phone,
        from_name="Asha",
        text="hi",
        button_id=None,
    )


async def test_inbound_message_skipped_for_merchant_not_yet_live(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    await WhatsAppBusinessAccountRepository(db_session).upsert(
        tenant, phone_number_id="PNID1", access_token_encrypted=encrypt("dummy-token")
    )
    await db_session.commit()

    merchant = await MerchantRepository(db_session).get(tenant.merchant_id)
    assert merchant is not None
    assert merchant.onboarding_status == "registered"  # not live -- still mid-onboarding

    sender = FakeSender()
    result = await handle_inbound_message(db_session, sender, _inbound())

    assert result.skipped_not_live is True
    assert result.reply_sent is False
    assert sender.button_calls == []


async def test_inbound_message_processed_once_merchant_is_live(db_session: AsyncSession) -> None:
    tenant = await _make_tenant(db_session)
    await WhatsAppBusinessAccountRepository(db_session).upsert(
        tenant, phone_number_id="PNID1", access_token_encrypted=encrypt("dummy-token")
    )
    merchant = await MerchantRepository(db_session).get(tenant.merchant_id)
    assert merchant is not None
    merchant.onboarding_status = "live"
    await db_session.commit()

    sender = FakeSender()
    result = await handle_inbound_message(db_session, sender, _inbound())

    assert result.skipped_not_live is False
    assert result.reply_sent is True
    assert len(sender.button_calls) == 1
