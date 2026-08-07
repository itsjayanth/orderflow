"""add order_number and merchant_order_counters

Revision ID: 425c10d1b38d
Revises: 5a6563afe0db
Create Date: 2026-08-07 22:41:06.537255

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '425c10d1b38d'
down_revision: Union[str, Sequence[str], None] = '5a6563afe0db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('merchant_order_counters',
    sa.Column('merchant_id', sa.Uuid(), nullable=False),
    sa.Column('next_order_number', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.merchant_id'], ),
    sa.PrimaryKeyConstraint('merchant_id')
    )

    # Nullable first -- existing rows have no order_number yet. Backfilled
    # below (per-merchant, ordered by placed_at) before the NOT NULL is
    # applied, so this is safe against a database that already has orders
    # (both local dev and the deployed Railway DB do).
    op.add_column('orders', sa.Column('order_number', sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE orders
        SET order_number = numbered.rn
        FROM (
            SELECT order_id, ROW_NUMBER() OVER (
                PARTITION BY merchant_id ORDER BY placed_at
            ) AS rn
            FROM orders
        ) AS numbered
        WHERE orders.order_id = numbered.order_id
        """
    )
    op.alter_column('orders', 'order_number', existing_type=sa.Integer(), nullable=False)
    op.create_unique_constraint(
        'uq_orders_merchant_order_number', 'orders', ['merchant_id', 'order_number']
    )

    # Seed each merchant's counter from whatever order_number the backfill
    # above assigned, so the next order created continues the sequence
    # instead of restarting at 1. Merchants with zero orders get no row
    # here -- OrderRepository._next_order_number's upsert creates one
    # lazily (starting at 1) the first time they get an order.
    op.execute(
        """
        INSERT INTO merchant_order_counters (merchant_id, next_order_number)
        SELECT merchant_id, MAX(order_number) + 1
        FROM orders
        GROUP BY merchant_id
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_orders_merchant_order_number', 'orders', type_='unique')
    op.drop_column('orders', 'order_number')
    op.drop_table('merchant_order_counters')
