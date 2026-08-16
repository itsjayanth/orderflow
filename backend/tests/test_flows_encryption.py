import base64
import json
import os

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from flows.domain.encryption import (
    FlowDecryptionError,
    decrypt_request,
    encrypt_response,
    generate_key_pair,
)

_OAEP_PADDING = padding.OAEP(
    mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None
)


def _simulate_meta_request(
    public_key_pem: str, payload: dict
) -> tuple[str, str, str, bytes, bytes]:
    """Builds a request the way WhatsApp's Flow client actually does, so the
    test proves our decrypt_request is compatible with the real protocol,
    not just symmetric with itself. Returns the three base64 fields plus
    the raw aes_key/iv for the test to check the response against."""
    public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    aes_key = os.urandom(16)
    iv = os.urandom(16)

    encrypted_aes_key = public_key.encrypt(aes_key, _OAEP_PADDING)  # type: ignore[union-attr]
    flow_data = AESGCM(aes_key).encrypt(iv, json.dumps(payload).encode("utf-8"), None)

    return (
        base64.b64encode(flow_data).decode("utf-8"),
        base64.b64encode(encrypted_aes_key).decode("utf-8"),
        base64.b64encode(iv).decode("utf-8"),
        aes_key,
        iv,
    )


def test_generate_key_pair_produces_valid_pem_pair() -> None:
    public_pem, private_pem = generate_key_pair()

    assert public_pem.startswith("-----BEGIN PUBLIC KEY-----")
    assert private_pem.startswith("-----BEGIN PRIVATE KEY-----")
    # Round-trips through the same loaders the real decrypt path uses.
    serialization.load_pem_public_key(public_pem.encode("utf-8"))
    serialization.load_pem_private_key(private_pem.encode("utf-8"), password=None)


def test_decrypt_request_recovers_payload_built_the_way_meta_builds_it() -> None:
    public_pem, private_pem = generate_key_pair()
    original = {"version": "3.0", "action": "ping"}
    flow_data_b64, aes_key_b64, iv_b64, expected_key, expected_iv = _simulate_meta_request(
        public_pem, original
    )

    payload, aes_key, iv = decrypt_request(
        encrypted_flow_data_b64=flow_data_b64,
        encrypted_aes_key_b64=aes_key_b64,
        initial_vector_b64=iv_b64,
        private_key_pem=private_pem,
    )

    assert payload == original
    assert aes_key == expected_key
    assert iv == expected_iv


def test_decrypt_request_raises_on_garbage_input() -> None:
    _, private_pem = generate_key_pair()

    with pytest.raises(FlowDecryptionError):
        decrypt_request(
            encrypted_flow_data_b64=base64.b64encode(b"not encrypted").decode(),
            encrypted_aes_key_b64=base64.b64encode(b"not an aes key").decode(),
            initial_vector_b64=base64.b64encode(b"0123456789012345").decode(),
            private_key_pem=private_pem,
        )


def test_decrypt_request_rejects_data_encrypted_under_a_different_keypair() -> None:
    """The AES key must have been RSA-encrypted under *our* public key --
    if it wasn't (e.g. our public key was rotated at Meta but this request
    was built against the old one), decryption must fail loudly, not
    silently produce garbage."""
    _, our_private_pem = generate_key_pair()
    someone_elses_public_pem, _ = generate_key_pair()
    flow_data_b64, aes_key_b64, iv_b64, _, _ = _simulate_meta_request(
        someone_elses_public_pem, {"action": "ping"}
    )

    with pytest.raises(FlowDecryptionError):
        decrypt_request(
            encrypted_flow_data_b64=flow_data_b64,
            encrypted_aes_key_b64=aes_key_b64,
            initial_vector_b64=iv_b64,
            private_key_pem=our_private_pem,
        )


def test_encrypt_response_is_decryptable_the_way_meta_decrypts_it() -> None:
    """Simulates the client side of the response leg: flip the *request*
    IV, AES-GCM-decrypt with the same key. If this doesn't recover the
    original response, WhatsApp wouldn't be able to render our screen."""
    aes_key = os.urandom(16)
    request_iv = os.urandom(16)
    response = {"screen": "MENU", "data": {"items": []}}

    encrypted_b64 = encrypt_response(response=response, aes_key=aes_key, iv=request_iv)

    flipped_iv = bytes(b ^ 0xFF for b in request_iv)
    decrypted = AESGCM(aes_key).decrypt(flipped_iv, base64.b64decode(encrypted_b64), None)
    assert json.loads(decrypted) == response


def test_encrypt_response_flips_iv_not_reuses_request_iv() -> None:
    aes_key = os.urandom(16)
    request_iv = os.urandom(16)
    response = {"screen": "MENU"}

    encrypted_b64 = encrypt_response(response=response, aes_key=aes_key, iv=request_iv)

    # Decrypting with the *unflipped* request IV must fail -- proves the
    # response is genuinely bound to a different IV, not accidentally
    # reusing the request's.
    with pytest.raises(Exception):  # noqa: B017 - cryptography raises InvalidTag, not ours to import
        AESGCM(aes_key).decrypt(request_iv, base64.b64decode(encrypted_b64), None)
