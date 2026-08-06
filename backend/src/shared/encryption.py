from functools import lru_cache

from cryptography.fernet import Fernet

from shared.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().secrets_encryption_key
    if not key:
        raise RuntimeError("SECRETS_ENCRYPTION_KEY is not set")
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
