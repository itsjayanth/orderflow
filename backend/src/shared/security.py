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


def create_access_token(staff_user_id: uuid.UUID, merchant_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": str(staff_user_id),
        "merchant_id": str(merchant_id),
        "type": "access",
        "iat": now,
        "exp": now + datetime.timedelta(minutes=settings.jwt_access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict[str, str]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
