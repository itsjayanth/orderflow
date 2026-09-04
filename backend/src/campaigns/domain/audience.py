import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from customers.domain.models import Customer
from orders.domain.models import Order
from shared.tenant import TenantContext

# {"kind": "all"} | {"kind": "ordered_within_days", "days": int} |
# {"kind": "no_order_within_days", "days": int} -- deliberately not the
# full Customer Segmentation Engine (a separate, not-yet-built P1 roadmap
# ticket). An unused "segment_id" key may also be present on the stored
# dict -- read by nothing here, an explicit extension point for that
# ticket to populate later without a migration.
_AUDIENCE_KINDS = ("all", "ordered_within_days", "no_order_within_days")


class InvalidAudienceFilterError(Exception):
    pass


def validate_audience_filter(audience_filter: dict[str, object]) -> None:
    kind = audience_filter.get("kind")
    if kind not in _AUDIENCE_KINDS:
        raise InvalidAudienceFilterError(
            f"audience_filter.kind must be one of {_AUDIENCE_KINDS}, got {kind!r}."
        )
    if kind in ("ordered_within_days", "no_order_within_days"):
        days = audience_filter.get("days")
        if not isinstance(days, int) or isinstance(days, bool) or days <= 0:
            raise InvalidAudienceFilterError(
                f"audience_filter.days must be a positive integer for kind={kind!r}."
            )


async def resolve_audience(
    session: AsyncSession,
    tenant: TenantContext,
    audience_filter: dict[str, object],
    *,
    now: datetime.datetime | None = None,
) -> list[Customer]:
    """Resolves an AudienceFilter dict into the matching, active Customer
    rows for `tenant` -- deliberately returns every match including a
    currently-opted-out customer (campaigns/domain/send_orchestrator.py is
    what turns that into a skipped_opted_out CampaignRecipient row, not a
    silent absence from the audience, so the delivery report can show it).

    ordered_within_days/no_order_within_days query Order.placed_at
    directly (a customer_id subquery), not Customer.last_order_at --
    that column is declared on the model but never actually written by
    any order-creation path in this codebase today (checked: neither
    OrderRepository.create nor ordering_flow/domain/checkout.py's
    perform_checkout touches it), so relying on it here would make both
    of these audience kinds silently return the wrong thing rather than
    fixing a pre-existing, unrelated dead column as a side effect of this
    feature."""
    now = now if now is not None else datetime.datetime.now(datetime.UTC)
    kind = audience_filter.get("kind")

    stmt = select(Customer).where(
        Customer.merchant_id == tenant.merchant_id, Customer.is_active.is_(True)
    )

    if kind in ("ordered_within_days", "no_order_within_days"):
        days = int(audience_filter["days"])  # type: ignore[call-overload]
        cutoff = now - datetime.timedelta(days=days)
        recent_customer_ids = select(Order.customer_id).where(
            Order.merchant_id == tenant.merchant_id, Order.placed_at >= cutoff
        )
        if kind == "ordered_within_days":
            stmt = stmt.where(Customer.customer_id.in_(recent_customer_ids))
        else:
            stmt = stmt.where(Customer.customer_id.not_in(recent_customer_ids))
    elif kind != "all":
        raise InvalidAudienceFilterError(f"Unknown audience_filter.kind {kind!r}.")

    result = await session.execute(stmt)
    return list(result.scalars().all())
