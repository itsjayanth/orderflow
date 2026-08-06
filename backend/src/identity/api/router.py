import uuid

import jwt
from fastapi import APIRouter, Cookie, HTTPException, Response, status

from identity.adapters.repository import MerchantRepository, StaffUserRepository
from identity.api.schemas import (
    AccessTokenResponse,
    LoginRequest,
    MerchantOut,
    MeResponse,
    RegisterRequest,
    StaffUserOut,
)
from identity.domain.auth import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    TokenPair,
    login,
    register_merchant,
    rotate_tokens,
)
from shared.config import get_settings
from shared.deps import CurrentStaffUserId, CurrentTenant, DbSession
from shared.security import decode_token

router = APIRouter(prefix="/api/v1/auth", tags=["identity"])

REFRESH_COOKIE_NAME = "orderflow_refresh_token"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    # The dashboard (Vercel) and API (Render/Railway/whichever host) are on
    # different origins in every deployed environment, so the browser only
    # sends this cookie back on cross-site fetches if SameSite=None -- which
    # itself requires Secure. Locally both run on http://localhost, same-site,
    # so Lax without Secure is correct there (browsers reject Secure cookies
    # over plain http).
    cross_site = settings.is_production
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=cross_site,
        samesite="none" if cross_site else "lax",
        max_age=settings.jwt_refresh_token_ttl_days * 24 * 60 * 60,
        path="/api/v1/auth",
    )


def _access_token_response(response: Response, tokens: TokenPair) -> AccessTokenResponse:
    _set_refresh_cookie(response, tokens.refresh_token)
    return AccessTokenResponse(access_token=tokens.access_token)


@router.post("/register", response_model=AccessTokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest, session: DbSession, response: Response
) -> AccessTokenResponse:
    try:
        _merchant, _staff_user, tokens = await register_merchant(
            session, body.business_name, body.owner_name, body.owner_contact, body.password
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An account with this contact already exists"
        ) from exc
    return _access_token_response(response, tokens)


@router.post("/login", response_model=AccessTokenResponse)
async def login_route(
    body: LoginRequest, session: DbSession, response: Response
) -> AccessTokenResponse:
    try:
        _staff_user, tokens = await login(session, body.email_or_phone, body.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid email/phone or password"
        ) from exc
    return _access_token_response(response, tokens)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    session: DbSession,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> AccessTokenResponse:
    if refresh_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing refresh token")

    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token"
        ) from exc

    try:
        tokens = await rotate_tokens(session, uuid.UUID(payload["sub"]))
    except InvalidCredentialsError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from exc
    return _access_token_response(response, tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")


@router.get("/me", response_model=MeResponse)
async def me(
    tenant: CurrentTenant, staff_user_id: CurrentStaffUserId, session: DbSession
) -> MeResponse:
    staff_user = await StaffUserRepository(session).get(staff_user_id)
    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    if staff_user is None or merchant is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account no longer exists")

    return MeResponse(
        staff_user=StaffUserOut.model_validate(staff_user),
        merchant=MerchantOut.model_validate(merchant),
    )
