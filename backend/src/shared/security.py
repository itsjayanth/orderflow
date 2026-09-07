import datetime
import uuid

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from shared.config import get_settings

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def _require_jwt_secret() -> str:
    """Fails closed rather than falling back to a guessable default -- the
    same convention shared/encryption.py's _fernet() uses for
    secrets_encryption_key."""
    secret = get_settings().jwt_secret
    if not secret:
        raise RuntimeError("JWT_SECRET is not set")
    return secret


def _create_token(
    staff_user_id: uuid.UUID, merchant_id: uuid.UUID, token_type: str, ttl: datetime.timedelta
) -> str:
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": str(staff_user_id),
        "merchant_id": str(merchant_id),
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _require_jwt_secret(), algorithm="HS256")


def create_access_token(staff_user_id: uuid.UUID, merchant_id: uuid.UUID) -> str:
    settings = get_settings()
    ttl = datetime.timedelta(minutes=settings.jwt_access_token_ttl_minutes)
    return _create_token(staff_user_id, merchant_id, "access", ttl)


def create_refresh_token(staff_user_id: uuid.UUID, merchant_id: uuid.UUID) -> str:
    settings = get_settings()
    ttl = datetime.timedelta(days=settings.jwt_refresh_token_ttl_days)
    return _create_token(staff_user_id, merchant_id, "refresh", ttl)


def decode_token(token: str, expected_type: str) -> dict[str, str]:
    payload = jwt.decode(token, _require_jwt_secret(), algorithms=["HS256"])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"expected a {expected_type} token")
    return payload
