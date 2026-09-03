import uuid

import jwt
from fastapi import APIRouter, Cookie, HTTPException, Response, status

from appointments.adapters.scheduling_repository import (
    AppointmentServiceRepository,
    MerchantAvailabilityRepository,
)
from identity.adapters.repository import MerchantRepository, StaffUserRepository
from identity.api.schemas import (
    AccessTokenResponse,
    AppointmentAvailabilitySettingsOut,
    AppointmentAvailabilitySettingsUpdate,
    AppointmentAvailabilityWindow,
    AppointmentServiceCreateRequest,
    AppointmentServiceOut,
    AppointmentServiceUpdateRequest,
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


@router.get("/appointment-availability", response_model=AppointmentAvailabilitySettingsOut)
async def get_appointment_availability_settings(
    tenant: CurrentTenant, session: DbSession
) -> AppointmentAvailabilitySettingsOut:
    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    if merchant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant not found")
    windows = await MerchantAvailabilityRepository(session).list(tenant)
    return AppointmentAvailabilitySettingsOut(
        timezone=merchant.timezone,
        windows=[AppointmentAvailabilityWindow.model_validate(w) for w in windows],
        reminder_offsets_hours=merchant.reminder_offsets_hours,
    )


@router.put("/appointment-availability", response_model=AppointmentAvailabilitySettingsOut)
async def update_appointment_availability_settings(
    body: AppointmentAvailabilitySettingsUpdate, tenant: CurrentTenant, session: DbSession
) -> AppointmentAvailabilitySettingsOut:
    """Full replace, not per-day patch -- see
    MerchantAvailabilityRepository.replace_all's docstring. The dashboard
    settings form always submits the complete weekly schedule; a weekday
    simply absent from `body.windows` means "closed that day"."""
    merchant = await MerchantRepository(session).get(tenant.merchant_id)
    if merchant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant not found")

    await MerchantRepository(session).update_timezone(tenant.merchant_id, body.timezone)
    await MerchantRepository(session).update_reminder_offsets_hours(
        tenant.merchant_id, body.reminder_offsets_hours
    )
    windows = await MerchantAvailabilityRepository(session).replace_all(
        tenant, windows=[w.model_dump() for w in body.windows]
    )
    await session.commit()
    return AppointmentAvailabilitySettingsOut(
        timezone=body.timezone,
        windows=[AppointmentAvailabilityWindow.model_validate(w) for w in windows],
        reminder_offsets_hours=body.reminder_offsets_hours,
    )


@router.get("/appointment-services", response_model=list[AppointmentServiceOut])
async def list_appointment_services(
    tenant: CurrentTenant, session: DbSession
) -> list[AppointmentServiceOut]:
    services = await AppointmentServiceRepository(session).list(tenant, include_inactive=True)
    return [AppointmentServiceOut.model_validate(s) for s in services]


@router.post(
    "/appointment-services",
    response_model=AppointmentServiceOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment_service(
    body: AppointmentServiceCreateRequest, tenant: CurrentTenant, session: DbSession
) -> AppointmentServiceOut:
    service = await AppointmentServiceRepository(session).create(
        tenant, name=body.name, duration_minutes=body.duration_minutes, price=body.price
    )
    await session.commit()
    return AppointmentServiceOut.model_validate(service)


@router.patch("/appointment-services/{service_id}", response_model=AppointmentServiceOut)
async def update_appointment_service(
    service_id: uuid.UUID,
    body: AppointmentServiceUpdateRequest,
    tenant: CurrentTenant,
    session: DbSession,
) -> AppointmentServiceOut:
    service = await AppointmentServiceRepository(session).update(
        tenant, service_id, **body.model_dump(exclude_unset=True)
    )
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    await session.commit()
    return AppointmentServiceOut.model_validate(service)


@router.delete("/appointment-services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment_service(
    service_id: uuid.UUID, tenant: CurrentTenant, session: DbSession
) -> None:
    deleted = await AppointmentServiceRepository(session).delete(tenant, service_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    await session.commit()
