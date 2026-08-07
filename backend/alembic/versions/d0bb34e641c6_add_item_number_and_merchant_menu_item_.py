"""add item_number and merchant_menu_item_counters

Revision ID: d0bb34e641c6
Revises: 425c10d1b38d
Create Date: 2026-08-07 23:20:06.417752

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0bb34e641c6'
down_revision: Union[str, Sequence[str], None] = '425c10d1b38d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('merchant_menu_item_counters',
    sa.Column('merchant_id', sa.Uuid(), nullable=False),
    sa.Column('next_item_number', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.merchant_id'], ),
    sa.PrimaryKeyConstraint('merchant_id')
    )

    # Nullable first -- existing menu_items have no item_number yet.
    # Backfilled below (per-merchant, ordered by created_at) before the NOT
    # NULL is applied, same approach as orders.order_number's migration --
    # safe against a database that already has rows (both local dev and the
    # deployed Railway DB do, including 35 real items just added to a live
    # merchant).
    op.add_column('menu_items', sa.Column('item_number', sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE menu_items
        SET item_number = numbered.rn
        FROM (
            SELECT menu_item_id, ROW_NUMBER() OVER (
                PARTITION BY merchant_id ORDER BY created_at
            ) AS rn
            FROM menu_items
        ) AS numbered
        WHERE menu_items.menu_item_id = numbered.menu_item_id
        """
    )
    op.alter_column('menu_items', 'item_number', existing_type=sa.Integer(), nullable=False)
    op.create_unique_constraint(
        'uq_menu_items_merchant_item_number', 'menu_items', ['merchant_id', 'item_number']
    )

    # Seed each merchant's counter from the backfilled max, so the next
    # item created continues the sequence instead of restarting at 1.
    # Merchants with zero items get no row here -- the repository's upsert
    # creates one lazily (starting at 1) on their first item.
    op.execute(
        """
        INSERT INTO merchant_menu_item_counters (merchant_id, next_item_number)
        SELECT merchant_id, MAX(item_number) + 1
        FROM menu_items
        GROUP BY merchant_id
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_menu_items_merchant_item_number', 'menu_items', type_='unique')
    op.drop_column('menu_items', 'item_number')
    op.drop_table('merchant_menu_item_counters')
