import datetime

from fastapi import APIRouter, HTTPException, status

from billing.adapters.gateway_selector import get_billing_gateway
from billing.adapters.repository import PlanRepository, SubscriptionRepository
from billing.api.schemas import (
    ChangePlanRequest,
    PlanOut,
    SubscribeRequest,
    SubscriptionCheckoutOut,
    SubscriptionOut,
)
from billing.domain.gating import billing_cycle_window, effective_order_cap, effective_tier
from billing.domain.models import Plan, Subscription
from orders.adapters.repository import OrderRepository
from shared.config import get_settings
from shared.deps import CurrentTenant, DbSession

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


def _plan_out(plan: Plan) -> PlanOut:
    return PlanOut(
        plan_id=plan.plan_id,
        tier=plan.tier,
        billing_interval=plan.billing_interval,
        display_name=plan.display_name,
        price_inr=plan.price_inr,
        order_cap=plan.order_cap,
        whatsapp_flow_enabled=plan.whatsapp_flow_enabled,
        branding_required=plan.branding_required,
    )


async def _build_subscription_out(
    session: DbSession, tenant: CurrentTenant, subscription: Subscription, plan: Plan
) -> SubscriptionOut:
    now = datetime.datetime.now(datetime.UTC)
    plans_by_tier = {p.tier: p for p in await PlanRepository(session).list_all()}
    tier = effective_tier(subscription, plan, now)
    order_cap = effective_order_cap(tier, plans_by_tier)

    cycle_start, cycle_end = billing_cycle_window(subscription, now)
    orders_used_this_cycle = await OrderRepository(session).count_since(
        tenant, cycle_start, cycle_end
    )

    return SubscriptionOut(
        merchant_id=subscription.merchant_id,
        plan=_plan_out(plan),
        status=subscription.status,
        trial_ends_at=subscription.trial_ends_at,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        past_due_since=subscription.past_due_since,
        cancel_at_period_end=subscription.cancel_at_period_end,
        orders_used_this_cycle=orders_used_this_cycle,
        order_cap=order_cap,
    )


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(session: DbSession) -> list[PlanOut]:
    """Deliberately no CurrentTenant dependency -- this codebase applies
    auth per-route (via a `tenant: CurrentTenant` parameter), not at the
    router or app level (dashboard_api_router mounts every sub-router with
    no `dependencies=[...]`), so simply omitting that parameter here is
    enough to make this endpoint callable with zero auth headers, as the
    public marketing pricing page needs."""
    plans = await PlanRepository(session).list_all()
    return [_plan_out(plan) for plan in plans]


@router.get("/subscription", response_model=SubscriptionOut)
async def get_subscription(tenant: CurrentTenant, session: DbSession) -> SubscriptionOut:
    subscription = await SubscriptionRepository(session).get(tenant)
    if subscription is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No subscription found")
    plan = await PlanRepository(session).get(subscription.plan_id)
    assert plan is not None
    return await _build_subscription_out(session, tenant, subscription, plan)


@router.post("/subscribe", response_model=SubscriptionCheckoutOut)
async def subscribe(
    body: SubscribeRequest, tenant: CurrentTenant, session: DbSession
) -> SubscriptionCheckoutOut:
    plan = await PlanRepository(session).get(body.plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")

    settings = get_settings()
    gateway = get_billing_gateway(
        settings.platform_razorpay_key_id,
        settings.platform_razorpay_key_secret,
        settings.platform_razorpay_webhook_secret,
    )
    checkout = gateway.create_subscription(plan=plan, merchant_id=tenant.merchant_id)

    subscription_repo = SubscriptionRepository(session)
    subscription = await subscription_repo.get(tenant)
    if subscription is None:
        subscription = await subscription_repo.create(
            tenant, plan_id=plan.plan_id, status="trialing", trial_ends_at=None
        )
    else:
        subscription.plan_id = plan.plan_id
    subscription.provider_subscription_id = checkout.provider_subscription_id
    await subscription_repo.save(subscription)
    await session.commit()

    return SubscriptionCheckoutOut(
        provider_subscription_id=checkout.provider_subscription_id,
        checkout_url=checkout.checkout_url,
    )


@router.post("/change-plan", response_model=SubscriptionOut)
async def change_plan(
    body: ChangePlanRequest, tenant: CurrentTenant, session: DbSession
) -> SubscriptionOut:
    subscription_repo = SubscriptionRepository(session)
    subscription = await subscription_repo.get(tenant)
    if subscription is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No subscription found")

    plan = await PlanRepository(session).get(body.plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")

    subscription.plan_id = plan.plan_id
    await subscription_repo.save(subscription)
    await session.commit()

    return await _build_subscription_out(session, tenant, subscription, plan)


@router.post("/cancel", response_model=SubscriptionOut)
async def cancel_subscription(tenant: CurrentTenant, session: DbSession) -> SubscriptionOut:
    subscription_repo = SubscriptionRepository(session)
    subscription = await subscription_repo.get(tenant)
    if subscription is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No subscription found")

    # Deferred to period end -- status itself doesn't change here, only
    # once the webhook (subscription.cancelled/halted) or the sweep job
    # confirms the period has actually ended.
    subscription.cancel_at_period_end = True
    await subscription_repo.save(subscription)
    await session.commit()

    plan = await PlanRepository(session).get(subscription.plan_id)
    assert plan is not None
    return await _build_subscription_out(session, tenant, subscription, plan)
