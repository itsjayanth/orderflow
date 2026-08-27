"""rename stale menu_items-derived index and constraint names

Revision ID: 9169aa688d5e
Revises: 74f76cb509a0
Create Date: 2026-08-26 18:44:25.963924

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9169aa688d5e'
down_revision: Union[str, Sequence[str], None] = '74f76cb509a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename indexes/constraints left over from the menu_items -> items and
    merchant_menu_item_counters -> merchant_item_counters table renames
    (Postgres RENAME TABLE does not rename the table's auto-named indexes
    and constraints, so they stayed on their old, now-stale names)."""
    op.execute("ALTER INDEX ix_menu_items_merchant_id RENAME TO ix_items_merchant_id")
    op.execute("ALTER INDEX menu_items_pkey RENAME TO items_pkey")
    op.execute(
        "ALTER INDEX uq_menu_items_merchant_item_number RENAME TO uq_items_merchant_item_number"
    )
    op.execute(
        "ALTER INDEX merchant_menu_item_counters_pkey RENAME TO merchant_item_counters_pkey"
    )


def downgrade() -> None:
    """Reverse the renames."""
    op.execute("ALTER INDEX ix_items_merchant_id RENAME TO ix_menu_items_merchant_id")
    op.execute("ALTER INDEX items_pkey RENAME TO menu_items_pkey")
    op.execute(
        "ALTER INDEX uq_items_merchant_item_number RENAME TO uq_menu_items_merchant_item_number"
    )
    op.execute(
        "ALTER INDEX merchant_item_counters_pkey RENAME TO merchant_menu_item_counters_pkey"
    )
