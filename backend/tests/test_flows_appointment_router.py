import base64
import json
import os
import uuid

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from customers.adapters.repository import CustomerRepository
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
    see test_flows_router.py / flows/domain/encryption.py's docstrings for
    the protocol. Returns the request body plus the aes_key/iv the test
    needs to decrypt the response with."""
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


async def _seed_merchant_with_appointment_flow_key(
    db_session: AsyncSession, *, business_name: str = "Varkey's"
) -> tuple[TenantContext, str]:
    merchant = await MerchantRepository(db_session).create(
        business_name=business_name, owner_contact="appointment-flow-test@example.com"
    )
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    await WhatsAppBusinessAccountRepository(db_session).upsert(
        tenant, phone_number_id="PNID1", access_token_encrypted=encrypt("dummy-token")
    )
    public_pem, private_pem = generate_key_pair()
    await WhatsAppBusinessAccountRepository(db_session).set_appointment_flow_credentials(
        tenant, flow_id="APPT_FLOW_1", private_key_encrypted=encrypt(private_pem)
    )
    await db_session.commit()
    return tenant, public_pem


async def test_appointment_ping_returns_active_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tenant, public_pem = await _seed_merchant_with_appointment_flow_key(db_session)
    request_body, aes_key, iv = _build_request(public_pem, {"version": "3.0", "action": "ping"})

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/appointment-data-exchange",
        json=request_body,
    )

    assert response.status_code == 200
    assert _decrypt_response(response.text, aes_key, iv) == {"data": {"status": "active"}}


async def test_appointment_init_returns_booking_screen(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tenant, public_pem = await _seed_merchant_with_appointment_flow_key(db_session)
    request_body, aes_key, iv = _build_request(public_pem, {"version": "3.0", "action": "INIT"})

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/appointment-data-exchange",
        json=request_body,
    )

    assert response.status_code == 200
    decrypted = _decrypt_response(response.text, aes_key, iv)
    assert decrypted["screen"] == "BOOKING"
    assert decrypted["data"]["business_name"] == "Varkey's"
    assert len(decrypted["data"]["date_options"]) == 14
    assert len(decrypted["data"]["time_options"]) == 22


async def test_appointment_bad_encryption_returns_421(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tenant, _ = await _seed_merchant_with_appointment_flow_key(db_session)

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/appointment-data-exchange",
        json={
            "encrypted_flow_data": base64.b64encode(b"garbage").decode(),
            "encrypted_aes_key": base64.b64encode(b"garbage").decode(),
            "initial_vector": base64.b64encode(b"0123456789012345").decode(),
        },
    )

    assert response.status_code == 421


async def test_appointment_unknown_merchant_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/whatsapp/flows/{uuid.uuid4()}/appointment-data-exchange",
        json={"encrypted_flow_data": "x", "encrypted_aes_key": "x", "initial_vector": "x"},
    )

    assert response.status_code == 404


async def test_appointment_init_prefills_name_and_email_for_returning_customer(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """flow_token carries the customer's WhatsApp number, set when the Flow
    is sent (conversation/domain/handler.py) -- the same shared identity-
    resolution entrypoint the order Flow's DETAILS screen already uses
    (test_flows_router.py's prefill tests)."""
    tenant, public_pem = await _seed_merchant_with_appointment_flow_key(db_session)
    await CustomerRepository(db_session).find_or_create(
        tenant, "919876543210", display_name="Asha"
    )
    # Simulates a returning customer previously giving an email through a
    # past booking -- update_profile_from_appointment is what would have
    # written this in a real flow; setting it directly here keeps this
    # test scoped to prefill, not booking.
    customer = await CustomerRepository(db_session).get_by_whatsapp_number(tenant, "919876543210")
    assert customer is not None
    customer.email = "asha@example.com"
    await db_session.commit()

    request_body, aes_key, iv = _build_request(
        public_pem,
        {"version": "3.0", "action": "INIT", "flow_token": "919876543210"},
    )

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/appointment-data-exchange",
        json=request_body,
    )

    assert response.status_code == 200
    decrypted = _decrypt_response(response.text, aes_key, iv)
    assert decrypted["data"]["saved_customer_name"] == "Asha"
    assert decrypted["data"]["saved_customer_email"] == "asha@example.com"


async def test_appointment_init_prefills_name_with_blank_email_when_customer_never_gave_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A customer who's only ever ordered food (never booked) has a name
    but no email on file -- that's an incomplete profile to prefill-then-
    fill-once, not an error."""
    tenant, public_pem = await _seed_merchant_with_appointment_flow_key(db_session)
    await CustomerRepository(db_session).find_or_create(
        tenant, "919876543210", display_name="Asha"
    )
    await db_session.commit()

    request_body, aes_key, iv = _build_request(
        public_pem, {"version": "3.0", "action": "INIT", "flow_token": "919876543210"}
    )

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/appointment-data-exchange",
        json=request_body,
    )

    assert response.status_code == 200
    decrypted = _decrypt_response(response.text, aes_key, iv)
    assert decrypted["data"]["saved_customer_name"] == "Asha"
    assert decrypted["data"]["saved_customer_email"] == ""


async def test_appointment_init_blank_prefill_for_new_customer(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tenant, public_pem = await _seed_merchant_with_appointment_flow_key(db_session)
    request_body, aes_key, iv = _build_request(
        public_pem,
        {"version": "3.0", "action": "INIT", "flow_token": "919876543299"},
    )

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/appointment-data-exchange",
        json=request_body,
    )

    assert response.status_code == 200
    decrypted = _decrypt_response(response.text, aes_key, iv)
    assert decrypted["data"]["saved_customer_name"] == ""
    assert decrypted["data"]["saved_customer_email"] == ""


async def test_appointment_init_missing_flow_token_falls_back_to_blank_no_500(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A malformed/missing flow_token must never 500 the Flow -- it just
    renders the BOOKING screen with nothing prefilled, same as a brand-new
    customer."""
    tenant, public_pem = await _seed_merchant_with_appointment_flow_key(db_session)
    request_body, aes_key, iv = _build_request(
        public_pem, {"version": "3.0", "action": "INIT"}
    )

    response = await client.post(
        f"/api/v1/whatsapp/flows/{tenant.merchant_id}/appointment-data-exchange",
        json=request_body,
    )

    assert response.status_code == 200
    decrypted = _decrypt_response(response.text, aes_key, iv)
    assert decrypted["screen"] == "BOOKING"
    assert decrypted["data"]["saved_customer_name"] == ""
    assert decrypted["data"]["saved_customer_email"] == ""
