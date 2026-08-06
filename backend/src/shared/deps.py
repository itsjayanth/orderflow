import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_session
from shared.security import decode_token
from shared.tenant import TenantContext

_bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_current_token_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> dict[str, str]:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        return decode_token(credentials.credentials, expected_type="access")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc


async def get_tenant_context(
    payload: Annotated[dict[str, str], Depends(get_current_token_payload)],
) -> TenantContext:
    return TenantContext(merchant_id=uuid.UUID(payload["merchant_id"]))


async def get_current_staff_user_id(
    payload: Annotated[dict[str, str], Depends(get_current_token_payload)],
) -> uuid.UUID:
    return uuid.UUID(payload["sub"])


CurrentTenant = Annotated[TenantContext, Depends(get_tenant_context)]
CurrentStaffUserId = Annotated[uuid.UUID, Depends(get_current_staff_user_id)]
