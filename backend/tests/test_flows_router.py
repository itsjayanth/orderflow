import base64
import json
import os
import uuid
from decimal import Decimal

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.repository import MenuItemRepository
from flows.domain.encryption import generate_key_pair
from identity.adapters.repository import MerchantRepository
from onboarding.adapters.repository import WhatsAppBusinessAccountRepository
from shared.encryption import encrypt
from shared.tenant import TenantContext

_OAEP_PADDING = padding.OAEP(
    mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None
)


def _build_request(public_key_pem: str, payload: dict) -> tuple[dict, bytes, bytes]:
    """Encrypts a request body the same way WhatsApp's Flow client does --
    see flows/domain/encryption.py's docstrings for the protocol. Returns
    the request body plus the aes_key/iv the test needs to decrypt the
    response with."""
    public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    aes_key = os.urandom(16)
    iv = os.urandom(16)
    encrypted_aes_key = public_key.encrypt(aes_key, _OAEP_PADDING)  # type: ignore[union-attr]
    flow_data = AESGCM(aes_key).encrypt(iv, json.dumps(payload).encode("utf-8"), None)
    request_body = {
        "encrypted_flow_data": base64.b64encode(flow_data).decode(),
        "encrypted_aes_key": base64.b64encode(encrypted_aes_key).decode(),
        "initial_vector": base64.b64encode(iv).decode(),
    }
    return request_body, aes_key, iv


def _decrypt_response(response_body: str, aes_key: bytes, iv: bytes) -> dict:
    flipped_iv = bytes(b ^ 0xFF for b in iv)
    decrypted = AESGCM(aes_key).decrypt(flipped_iv, base64.b64decode(response_body), None)
    return json.loads(decrypted)


async def _seed_merchant_with_flow_key(
    db_session: AsyncSession, *, business_name: str = "Varkey's"
) -> tuple[TenantContext, str]:
    merchant = await MerchantRepository(db_session).create(
        business_name=business_name, owner_contact="flow-test@example.com"
    )
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    await WhatsAppBusinessAccountRepository(db_session).upsert(
        tenant, phone_number_id="PNID1", access_token_encrypted=encrypt("dummy-token")
    )
    public_pem, private_pem = generate_key_pair()
    await WhatsAppBusinessAccountRepository(db_session).set_flow_credentials(
        tenant, flow_id="FLOW_1", private_key_encrypted=encrypt(private_pem)
    )
    await db_session.commit()
    return tenant, public_pem


async def test_ping_returns_active_status(client: AsyncClient, db_session: AsyncSession) -> None:
    tenant, public_pem = await _seed_merchant_with_flow_key(db_session)
    request_body, aes_key, iv = _build_request(public_pem, {"version": "3.0", "action": "ping"})

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/data-exchange", json=request_body
    )

    assert response.status_code == 200
    assert _decrypt_response(response.text, aes_key, iv) == {"data": {"status": "active"}}


async def test_init_returns_menu_screen_with_available_items(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tenant, public_pem = await _seed_merchant_with_flow_key(db_session)
    await MenuItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    await db_session.commit()
    request_body, aes_key, iv = _build_request(public_pem, {"version": "3.0", "action": "INIT"})

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/data-exchange", json=request_body
    )

    assert response.status_code == 200
    decrypted = _decrypt_response(response.text, aes_key, iv)
    assert decrypted["screen"] == "MENU"
    assert decrypted["data"]["business_name"] == "Varkey's"
    assert len(decrypted["data"]["menu_options"]) == 1
    assert "Butter Chicken" in decrypted["data"]["menu_options"][0]["title"]


async def test_data_exchange_from_menu_returns_cart_summary(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tenant, public_pem = await _seed_merchant_with_flow_key(db_session)
    menu_item = await MenuItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    await db_session.commit()
    request_body, aes_key, iv = _build_request(
        public_pem,
        {
            "version": "3.0",
            "action": "data_exchange",
            "screen": "MENU",
            "data": {"selected_items": [str(menu_item.menu_item_id)]},
        },
    )

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/data-exchange", json=request_body
    )

    assert response.status_code == 200
    decrypted = _decrypt_response(response.text, aes_key, iv)
    assert decrypted["screen"] == "DETAILS"
    assert "Butter Chicken" in decrypted["data"]["cart_summary"]
    assert "Total: Rs 349.00" in decrypted["data"]["cart_summary"]


async def test_data_exchange_with_no_items_falls_back_to_menu(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tenant, public_pem = await _seed_merchant_with_flow_key(db_session)
    await MenuItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    await db_session.commit()
    request_body, aes_key, iv = _build_request(
        public_pem,
        {
            "version": "3.0",
            "action": "data_exchange",
            "screen": "MENU",
            "data": {"selected_items": []},
        },
    )

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/data-exchange", json=request_body
    )

    assert response.status_code == 200
    decrypted = _decrypt_response(response.text, aes_key, iv)
    assert decrypted["screen"] == "MENU"


async def test_bad_encryption_returns_421(client: AsyncClient, db_session: AsyncSession) -> None:
    tenant, _ = await _seed_merchant_with_flow_key(db_session)

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/data-exchange",
        json={
            "encrypted_flow_data": base64.b64encode(b"garbage").decode(),
            "encrypted_aes_key": base64.b64encode(b"garbage").decode(),
            "initial_vector": base64.b64encode(b"0123456789012345").decode(),
        },
    )

    assert response.status_code == 421


async def test_unknown_merchant_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/whatsapp/flows/{uuid.uuid4()}/data-exchange",
        json={"encrypted_flow_data": "x", "encrypted_aes_key": "x", "initial_vector": "x"},
    )

    assert response.status_code == 404
