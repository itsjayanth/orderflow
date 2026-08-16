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
from customers.adapters.repository import AddressRepository, CustomerRepository
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


async def test_init_returns_category_screen(client: AsyncClient, db_session: AsyncSession) -> None:
    tenant, public_pem = await _seed_merchant_with_flow_key(db_session)
    await MenuItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    await MenuItemRepository(db_session).create(
        tenant, category="Breads", name="Naan", price=Decimal("40.00")
    )
    await db_session.commit()
    request_body, aes_key, iv = _build_request(public_pem, {"version": "3.0", "action": "INIT"})

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/data-exchange", json=request_body
    )

    assert response.status_code == 200
    decrypted = _decrypt_response(response.text, aes_key, iv)
    assert decrypted["screen"] == "CATEGORY"
    assert decrypted["data"]["business_name"] == "Varkey's"
    assert decrypted["data"]["categories"] == [
        {"id": "Mains", "title": "Mains"},
        {"id": "Breads", "title": "Breads"},
    ]


async def test_data_exchange_from_category_returns_filtered_items(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tenant, public_pem = await _seed_merchant_with_flow_key(db_session)
    await MenuItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    await MenuItemRepository(db_session).create(
        tenant, category="Breads", name="Naan", price=Decimal("40.00")
    )
    await db_session.commit()
    request_body, aes_key, iv = _build_request(
        public_pem,
        {
            "version": "3.0",
            "action": "data_exchange",
            "screen": "CATEGORY",
            "data": {"category": "Mains"},
        },
    )

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/data-exchange", json=request_body
    )

    assert response.status_code == 200
    decrypted = _decrypt_response(response.text, aes_key, iv)
    assert decrypted["screen"] == "ITEMS"
    assert decrypted["data"]["category_name"] == "Mains"
    assert len(decrypted["data"]["menu_options"]) == 1
    assert "Butter Chicken" in decrypted["data"]["menu_options"][0]["title"]


async def test_data_exchange_from_items_returns_cart_summary_and_blank_address(
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
            "screen": "ITEMS",
            "data": {"selected_items": [str(menu_item.menu_item_id)]},
            "flow_token": "919876543210",
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
    assert decrypted["data"]["saved_address_line1"] == ""
    assert decrypted["data"]["has_saved_address"] == "false"
    assert decrypted["data"]["saved_customer_name"] == ""
    assert decrypted["data"]["saved_contact_choice"] == "same"


async def test_data_exchange_from_items_prefills_saved_address_for_returning_customer(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tenant, public_pem = await _seed_merchant_with_flow_key(db_session)
    menu_item = await MenuItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    customer = await CustomerRepository(db_session).find_or_create(
        tenant, "919876543210", display_name="Asha"
    )
    await AddressRepository(db_session).create(
        tenant,
        customer_id=customer.customer_id,
        label="Home",
        line1="12 MG Road",
        city="Bengaluru",
        pincode="560001",
        is_default=True,
    )
    await db_session.commit()
    request_body, aes_key, iv = _build_request(
        public_pem,
        {
            "version": "3.0",
            "action": "data_exchange",
            "screen": "ITEMS",
            "data": {"selected_items": [str(menu_item.menu_item_id)]},
            "flow_token": "919876543210",
        },
    )

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/data-exchange", json=request_body
    )

    assert response.status_code == 200
    decrypted = _decrypt_response(response.text, aes_key, iv)
    assert decrypted["data"]["saved_address_line1"] == "12 MG Road"
    assert decrypted["data"]["saved_address_city"] == "Bengaluru"
    assert decrypted["data"]["saved_address_pincode"] == "560001"
    assert decrypted["data"]["has_saved_address"] == "true"
    assert decrypted["data"]["saved_address_display"] == "12 MG Road, Bengaluru - 560001"
    assert decrypted["data"]["saved_customer_name"] == "Asha"
    assert decrypted["data"]["saved_contact_choice"] == "same"


async def test_data_exchange_from_items_prefills_contact_choice_when_customer_has_alt_number(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tenant, public_pem = await _seed_merchant_with_flow_key(db_session)
    menu_item = await MenuItemRepository(db_session).create(
        tenant, category="Mains", name="Butter Chicken", price=Decimal("349.00")
    )
    customer = await CustomerRepository(db_session).find_or_create(tenant, "919876543210")
    await CustomerRepository(db_session).update_contact_details(
        customer, display_name=None, default_contact_phone="919999999999"
    )
    await db_session.commit()
    request_body, aes_key, iv = _build_request(
        public_pem,
        {
            "version": "3.0",
            "action": "data_exchange",
            "screen": "ITEMS",
            "data": {"selected_items": [str(menu_item.menu_item_id)]},
            "flow_token": "919876543210",
        },
    )

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/data-exchange", json=request_body
    )

    assert response.status_code == 200
    decrypted = _decrypt_response(response.text, aes_key, iv)
    assert decrypted["data"]["saved_contact_choice"] == "different"
    assert decrypted["data"]["saved_contact_phone"] == "919999999999"


async def test_data_exchange_with_no_items_falls_back_to_category(
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
            "screen": "ITEMS",
            "data": {"selected_items": []},
        },
    )

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/data-exchange", json=request_body
    )

    assert response.status_code == 200
    decrypted = _decrypt_response(response.text, aes_key, iv)
    assert decrypted["screen"] == "CATEGORY"


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
