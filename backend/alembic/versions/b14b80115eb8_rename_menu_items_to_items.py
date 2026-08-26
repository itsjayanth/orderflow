"""rename menu_items to items

Revision ID: b14b80115eb8
Revises: 50fa02971d49
Create Date: 2026-08-26 18:13:18.172105

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b14b80115eb8'
down_revision: Union[str, Sequence[str], None] = '50fa02971d49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Straight renames (table/column), not additive-then-swap -- preserves
    every existing row (including the real Varkey's merchant data, see
    docs/generic-platform-migration.md) since a RENAME isn't a destructive
    drop, and this app's pre-deploy migration gate means no old-code reader
    is ever running concurrently against the old names.
    """
    op.rename_table('menu_items', 'items')
    op.alter_column('items', 'menu_item_id', new_column_name='item_id')
    op.rename_table('merchant_menu_item_counters', 'merchant_item_counters')
    op.alter_column('order_items', 'menu_item_id', new_column_name='item_id')


def downgrade() -> None:
    """Downgrade schema -- exact reverse of upgrade()."""
    op.alter_column('order_items', 'item_id', new_column_name='menu_item_id')
    op.rename_table('merchant_item_counters', 'merchant_menu_item_counters')
    op.alter_column('items', 'item_id', new_column_name='menu_item_id')
    op.rename_table('items', 'menu_items')
