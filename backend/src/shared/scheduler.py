import datetime
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from orders.adapters.repository import OrderRepository
from orders.domain.state_machine import transition_payment_status
from shared.config import get_settings
from shared.db import SessionFactory

logger = logging.getLogger(__name__)


async def sweep_abandoned_orders() -> None:
    """Timeout sweep from ARCHITECTURE.md Section 7a/Section 10 -- orders
    stuck in awaiting_payment past the threshold (no webhook, no retry)
    are cancelled so they don't sit in limbo forever."""
    settings = get_settings()
    threshold = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
        minutes=settings.abandoned_order_timeout_minutes
    )

    async with SessionFactory() as session:
        repo = OrderRepository(session)
        stale_orders = await repo.list_stale_awaiting_payment(threshold)
        for order in stale_orders:
            transition_payment_status(order, "cancelled")
        if stale_orders:
            await session.commit()
            logger.info("Cancelled %d abandoned order(s)", len(stale_orders))


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(sweep_abandoned_orders, "interval", minutes=5, id="sweep_abandoned_orders")
    return scheduler
