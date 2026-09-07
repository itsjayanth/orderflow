import datetime
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from billing.adapters.repository import PlanRepository, SubscriptionRepository
from identity.adapters.repository import (
    MerchantRepository,
    RevokedRefreshTokenRepository,
    StaffUserRepository,
)
from identity.domain.models import Merchant, StaffUser
from shared.config import get_settings
from shared.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from shared.tenant import TenantContext

logger = logging.getLogger(__name__)


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class RefreshTokenReusedError(InvalidCredentialsError):
    """Raised when a refresh token whose `jti` is already on the revoked
    denylist is presented again -- either logged-out-then-reused, or (more
    concerning) a token already rotated away and reused, which is the reuse
    -detection signal a rotation-tracking denylist gives for free: the old
    token only ever gets used again if it leaked and someone else has it,
    since the legitimate client moved on to the token rotate_tokens handed
    back. A subclass of InvalidCredentialsError so existing callers that
    only care about "reject the request" keep working unchanged; callers
    that want to log/alert on reuse specifically can catch this instead."""


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str


def _issue_tokens(staff_user: StaffUser) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(staff_user.staff_user_id, staff_user.merchant_id),
        refresh_token=create_refresh_token(staff_user.staff_user_id, staff_user.merchant_id),
    )


async def register_merchant(
    session: AsyncSession,
    business_name: str,
    owner_name: str,
    owner_contact: str,
    password: str,
) -> tuple[Merchant, StaffUser, TokenPair]:
    staff_repo = StaffUserRepository(session)
    if await staff_repo.get_by_email_or_phone(owner_contact) is not None:
        raise EmailAlreadyRegisteredError(owner_contact)

    merchant_repo = MerchantRepository(session)
    merchant = await merchant_repo.create(business_name=business_name, owner_contact=owner_contact)
    staff_user = await staff_repo.create(
        merchant_id=merchant.merchant_id,
        name=owner_name,
        email_or_phone=owner_contact,
        password_hash=hash_password(password),
        role="owner",
    )

    # Every merchant starts a Growth-tier trial the moment they register --
    # not gated behind onboarding's `live` status, which is an independent
    # concern (see billing/domain/gating.py's docstring: no order can flow
    # before `live` regardless of subscription status, so starting the
    # trial clock here doesn't leak any value early, and it matches the
    # plain "14-day free trial" mental model a merchant expects from the
    # moment they sign up). Same transaction as Merchant/StaffUser above.
    settings = get_settings()
    tenant = TenantContext(merchant_id=merchant.merchant_id)
    growth_plan = await PlanRepository(session).get_by_tier_and_interval("growth", "monthly")
    assert growth_plan is not None, "billing_plans seed migration must have run"
    await SubscriptionRepository(session).create(
        tenant,
        plan_id=growth_plan.plan_id,
        status="trialing",
        trial_ends_at=datetime.datetime.now(datetime.UTC)
        + datetime.timedelta(days=settings.trial_period_days),
    )

    await session.commit()
    return merchant, staff_user, _issue_tokens(staff_user)


async def login(
    session: AsyncSession, email_or_phone: str, password: str
) -> tuple[StaffUser, TokenPair]:
    staff_repo = StaffUserRepository(session)
    staff_user = await staff_repo.get_by_email_or_phone(email_or_phone)
    if staff_user is None or not verify_password(password, staff_user.password_hash):
        raise InvalidCredentialsError

    staff_user.last_login_at = datetime.datetime.now(datetime.UTC)
    await session.commit()
    return staff_user, _issue_tokens(staff_user)


async def rotate_tokens(
    session: AsyncSession,
    staff_user_id: uuid.UUID,
    refresh_jti: uuid.UUID,
    refresh_expires_at: datetime.datetime,
) -> TokenPair:
    """Issues a fresh access/refresh pair and revokes the refresh token
    being rotated away, so it can't be replayed for another rotation once
    the client has moved on to the new one. `refresh_jti`/`refresh_expires_at`
    come from the caller's already-decoded refresh token (the `jti`/`exp`
    claims every token carries -- see shared/security.py's _create_token).

    Reuse detection: if `refresh_jti` is already on the denylist -- either
    because this exact token was already rotated away once, or because the
    staff user logged out with it -- that means someone is presenting a
    refresh token that should no longer exist from the legitimate client's
    perspective. Raise RefreshTokenReusedError rather than silently
    re-revoking and issuing a fresh pair anyway, which would let a stolen
    token keep working forever just by re-presenting it."""
    revoked_repo = RevokedRefreshTokenRepository(session)
    if await revoked_repo.is_revoked(refresh_jti):
        logger.warning(
            "Refresh token reuse detected for staff_user_id=%s jti=%s",
            staff_user_id,
            refresh_jti,
        )
        raise RefreshTokenReusedError

    staff_repo = StaffUserRepository(session)
    staff_user = await staff_repo.get(staff_user_id)
    if staff_user is None:
        raise InvalidCredentialsError

    await revoked_repo.revoke(
        refresh_jti, staff_user.staff_user_id, staff_user.merchant_id, refresh_expires_at
    )
    tokens = _issue_tokens(staff_user)
    await session.commit()
    return tokens


async def revoke_refresh_token(
    session: AsyncSession,
    staff_user_id: uuid.UUID,
    merchant_id: uuid.UUID,
    refresh_jti: uuid.UUID,
    refresh_expires_at: datetime.datetime,
) -> None:
    """Backs the logout endpoint: adds the presented refresh token's `jti`
    to the denylist so it stops working immediately, rather than staying
    valid until its natural jwt_refresh_token_ttl_days expiry regardless of
    "logout". Named distinctly from the router's `logout` handler (which
    also owns the client-side cookie deletion) to avoid a name collision on
    import."""
    await RevokedRefreshTokenRepository(session).revoke(
        refresh_jti, staff_user_id, merchant_id, refresh_expires_at
    )
    await session.commit()
