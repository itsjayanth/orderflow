import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import app
from conversation.adapters.whatsapp_client import WhatsAppSender, get_whatsapp_sender
from conversation.domain.models import ProcessedWhatsAppMessage
from identity.adapters.repository import MerchantRepository
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from shared.encryption import encrypt
from shared.tenant import TenantContext


class RecordingSender(WhatsAppSender):
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send_text(
        self, *, phone_number_id: str, access_token: str, to: str, body: str
    ) -> bool:
        self.calls.append({"kind": "text", "to": to, "body": body})
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
        self.calls.append({"kind": "buttons", "to": to, "body": body})
        return True


def _override_sender() -> RecordingSender:
    sender = RecordingSender()
    app.dependency_overrides[get_whatsapp_sender] = lambda: sender
    return sender


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


async def _mark_live(db_session: AsyncSession, tenant: TenantContext) -> None:
    """These tests exercise webhook routing/dedup, not onboarding
    progression -- jump straight to "live" so the handler's onboarding-status
    guard doesn't reject the inbound message."""
    merchant = await MerchantRepository(db_session).get(tenant.merchant_id)
    assert merchant is not None
    merchant.onboarding_status = "live"
    await db_session.commit()


def _webhook_body(*, phone_number_id: str, message_id: str, from_phone: str, text: str) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_1",
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": phone_number_id},
                            "contacts": [{"profile": {"name": "Asha"}, "wa_id": from_phone}],
                            "messages": [
                                {
                                    "from": from_phone,
                                    "id": message_id,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


async def test_verify_webhook_with_correct_token(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "dev-verify-token",
            "hub.challenge": "12345",
        },
    )

    assert response.status_code == 200
    assert response.text == "12345"


async def test_verify_webhook_with_wrong_token_returns_403(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "12345",
        },
    )

    assert response.status_code == 403


async def test_inbound_webhook_routes_to_correct_merchant_and_replies(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await WhatsAppBusinessAccountRepository(db_session).upsert(
        tenant, phone_number_id="PNID_E2E", access_token_encrypted=encrypt("dummy-token")
    )
    await db_session.commit()
    await _mark_live(db_session, tenant)

    sender = _override_sender()
    try:
        response = await client.post(
            "/api/v1/whatsapp/webhook",
            json=_webhook_body(
                phone_number_id="PNID_E2E",
                message_id="wamid.e2e1",
                from_phone="919876543210",
                text="hi",
            ),
        )

        assert response.status_code == 200
        assert len(sender.calls) == 1
        assert sender.calls[0]["kind"] == "buttons"
    finally:
        app.dependency_overrides.pop(get_whatsapp_sender, None)


async def test_inbound_webhook_for_unknown_number_does_not_crash(client: AsyncClient) -> None:
    sender = _override_sender()
    try:
        response = await client.post(
            "/api/v1/whatsapp/webhook",
            json=_webhook_body(
                phone_number_id="NOT_REGISTERED",
                message_id="wamid.unknown1",
                from_phone="919876543210",
                text="hi",
            ),
        )

        assert response.status_code == 200
        assert sender.calls == []
    finally:
        app.dependency_overrides.pop(get_whatsapp_sender, None)


async def test_redelivered_webhook_is_deduped(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await _register(client)
    tenant = await _tenant_for(client, tokens)
    await WhatsAppBusinessAccountRepository(db_session).upsert(
        tenant, phone_number_id="PNID_DUP", access_token_encrypted=encrypt("dummy-token")
    )
    await db_session.commit()
    await _mark_live(db_session, tenant)

    sender = _override_sender()
    try:
        body = _webhook_body(
            phone_number_id="PNID_DUP",
            message_id="wamid.dup1",
            from_phone="919876543210",
            text="hi",
        )

        await client.post("/api/v1/whatsapp/webhook", json=body)
        await client.post("/api/v1/whatsapp/webhook", json=body)

        assert len(sender.calls) == 1

        result = await db_session.execute(
            select(ProcessedWhatsAppMessage).where(
                ProcessedWhatsAppMessage.whatsapp_message_id == "wamid.dup1"
            )
        )
        assert len(result.scalars().all()) == 1
    finally:
        app.dependency_overrides.pop(get_whatsapp_sender, None)
