import datetime
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from billing.adapters.repository import PlanRepository, SubscriptionRepository
from identity.adapters.repository import MerchantRepository, StaffUserRepository
from identity.domain.models import Merchant, StaffUser
from shared.config import get_settings
from shared.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from shared.tenant import TenantContext


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


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


async def rotate_tokens(session: AsyncSession, staff_user_id: uuid.UUID) -> TokenPair:
    staff_repo = StaffUserRepository(session)
    staff_user = await staff_repo.get(staff_user_id)
    if staff_user is None:
        raise InvalidCredentialsError
    return _issue_tokens(staff_user)
