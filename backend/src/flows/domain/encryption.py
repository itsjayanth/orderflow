import base64
import json
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_OAEP_PADDING = padding.OAEP(
    mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None
)


class FlowDecryptionError(Exception):
    """Raised when a Flow data-exchange request can't be decrypted -- a
    corrupt payload, or (per Meta's spec) a request encrypted against a
    public key we've since rotated. flows/api/router.py returns HTTP 421
    for this specifically, which tells WhatsApp to re-fetch our current
    public key and retry, rather than treating it as a generic failure."""


def generate_key_pair() -> tuple[str, str]:
    """Returns (public_key_pem, private_key_pem) for a fresh 2048-bit RSA
    pair. Called once per merchant by scripts/setup_whatsapp_flow.py -- the
    public half is uploaded to Meta (POST /{phone_number_id}/whatsapp_business_encryption),
    the private half is Fernet-encrypted and stored on WhatsAppBusinessAccount."""
    private_key = generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return public_pem, private_pem


def decrypt_request(
    *,
    encrypted_flow_data_b64: str,
    encrypted_aes_key_b64: str,
    initial_vector_b64: str,
    private_key_pem: str,
) -> tuple[dict[str, Any], bytes, bytes]:
    """Decrypts a WhatsApp Flow data-exchange request (data_api_version
    3.0): the AES key travels RSA-OAEP-SHA256-encrypted under our public
    key, the actual payload is AES-128-GCM-encrypted under that AES key
    (auth tag appended to the ciphertext, per Meta's spec -- `AESGCM`
    already expects and handles that layout, no manual tag-splitting
    needed). Returns (payload, aes_key, iv) -- the caller needs aes_key and
    the *original* iv again to encrypt the response."""
    try:
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"), password=None
        )
        aes_key = private_key.decrypt(  # type: ignore[union-attr]
            base64.b64decode(encrypted_aes_key_b64), _OAEP_PADDING
        )

        iv = base64.b64decode(initial_vector_b64)
        flow_data = base64.b64decode(encrypted_flow_data_b64)
        plaintext = AESGCM(aes_key).decrypt(iv, flow_data, None)

        payload: dict[str, Any] = json.loads(plaintext.decode("utf-8"))
        return payload, aes_key, iv
    except Exception as exc:
        raise FlowDecryptionError(str(exc)) from exc


def encrypt_response(*, response: dict[str, Any], aes_key: bytes, iv: bytes) -> str:
    """Encrypts a data-exchange response per Meta's spec: same AES key, but
    the *original* IV with every byte flipped (XOR 0xFF) -- reusing the
    request IV unflipped would let an attacker who captured one exchange
    replay it as the other direction. Returns the base64 string to send
    back verbatim as a `text/plain` body (not wrapped in JSON)."""
    flipped_iv = bytes(b ^ 0xFF for b in iv)
    ciphertext = AESGCM(aes_key).encrypt(flipped_iv, json.dumps(response).encode("utf-8"), None)
    return base64.b64encode(ciphertext).decode("utf-8")
