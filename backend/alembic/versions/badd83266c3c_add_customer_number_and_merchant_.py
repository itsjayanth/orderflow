"""add customer_number and merchant_customer_counters

Revision ID: badd83266c3c
Revises: 510663d692cb
Create Date: 2026-08-08 12:26:28.080836

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'badd83266c3c'
down_revision: Union[str, Sequence[str], None] = '510663d692cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('merchant_customer_counters',
    sa.Column('merchant_id', sa.Uuid(), nullable=False),
    sa.Column('next_customer_number', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.merchant_id'], ),
    sa.PrimaryKeyConstraint('merchant_id')
    )

    # Nullable first -- existing customers have no customer_number yet.
    # Backfilled below (per-merchant, ordered by first_seen_at) before the
    # NOT NULL is applied, same approach as orders.order_number and
    # menu_items.item_number's migrations -- safe against a database that
    # already has rows (both local dev and the deployed Railway DB do,
    # including real customers on the live Varkey's merchant).
    op.add_column('customers', sa.Column('customer_number', sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE customers
        SET customer_number = numbered.rn
        FROM (
            SELECT customer_id, ROW_NUMBER() OVER (
                PARTITION BY merchant_id ORDER BY first_seen_at
            ) AS rn
            FROM customers
        ) AS numbered
        WHERE customers.customer_id = numbered.customer_id
        """
    )
    op.alter_column('customers', 'customer_number', existing_type=sa.Integer(), nullable=False)
    op.create_unique_constraint(
        'uq_customers_merchant_number', 'customers', ['merchant_id', 'customer_number']
    )

    # Seed each merchant's counter from the backfilled max, so the next
    # customer created continues the sequence instead of restarting at 1.
    # Merchants with zero customers get no row here -- the repository's
    # upsert creates one lazily (starting at 1) on their first customer.
    op.execute(
        """
        INSERT INTO merchant_customer_counters (merchant_id, next_customer_number)
        SELECT merchant_id, MAX(customer_number) + 1
        FROM customers
        GROUP BY merchant_id
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_customers_merchant_number', 'customers', type_='unique')
    op.drop_column('customers', 'customer_number')
    op.drop_table('merchant_customer_counters')
