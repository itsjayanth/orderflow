import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from identity.adapters.repository import MerchantRepository
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


async def get_public_tenant(merchant_id: uuid.UUID, session: DbSession) -> TenantContext:
    """Tenant resolution for the public, unauthenticated customer-facing
    ordering endpoints -- there's no JWT here, so the merchant_id path
    parameter is the tenant boundary instead. Mirrors get_tenant_context's
    404-on-unknown-merchant behavior so every public endpoint gets it for
    free instead of hand-rolling the lookup."""
    merchant = await MerchantRepository(session).get(merchant_id)
    if merchant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant not found")
    return TenantContext(merchant_id=merchant.merchant_id)


CurrentTenant = Annotated[TenantContext, Depends(get_tenant_context)]
CurrentStaffUserId = Annotated[uuid.UUID, Depends(get_current_staff_user_id)]
PublicTenant = Annotated[TenantContext, Depends(get_public_tenant)]
