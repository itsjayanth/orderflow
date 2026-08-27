"""rename preparing fulfillment status to processing

Revision ID: 70e512b414d0
Revises: 9169aa688d5e
Create Date: 2026-08-26 22:33:17.468944

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '70e512b414d0'
down_revision: Union[str, Sequence[str], None] = '9169aa688d5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Data-only migration: rename the "preparing" fulfillment-status value
    to "processing" everywhere it's stored as a plain string (fulfillment_status
    is a String(32) column, not a Postgres enum type, so no ALTER TYPE is
    needed) -- orders.fulfillment_status, order_status_events.from_status/
    to_status (the append-only audit trail), and notification_templates.
    notification_kind (any merchant-customized "order_preparing" template
    row). Straight UPDATE, not additive/backfill, per the same reasoning as
    the earlier renames in this migration series: this app runs its
    migration as a pre-deploy gate before new code takes traffic, so there's
    no window where old code reads the old value."""
    op.execute("UPDATE orders SET fulfillment_status = 'processing' WHERE fulfillment_status = 'preparing'")
    op.execute("UPDATE order_status_events SET from_status = 'processing' WHERE from_status = 'preparing'")
    op.execute("UPDATE order_status_events SET to_status = 'processing' WHERE to_status = 'preparing'")
    op.execute(
        "UPDATE notification_templates SET notification_kind = 'order_processing' "
        "WHERE notification_kind = 'order_preparing'"
    )


def downgrade() -> None:
    """Reverse the data rename."""
    op.execute("UPDATE orders SET fulfillment_status = 'preparing' WHERE fulfillment_status = 'processing'")
    op.execute("UPDATE order_status_events SET from_status = 'preparing' WHERE from_status = 'processing'")
    op.execute("UPDATE order_status_events SET to_status = 'preparing' WHERE to_status = 'processing'")
    op.execute(
        "UPDATE notification_templates SET notification_kind = 'order_preparing' "
        "WHERE notification_kind = 'order_processing'"
    )
