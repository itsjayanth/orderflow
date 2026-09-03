"""add last_payment_method to customers

Revision ID: 215b9cb77f05
Revises: ba5a0297c201
Create Date: 2026-09-03 10:56:54.137039

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '215b9cb77f05'
down_revision: Union[str, Sequence[str], None] = 'ba5a0297c201'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable, no default backfill needed -- None already means "no
    # preferred method on file yet" for every existing customer row, which
    # is exactly the fallback the prefill UI already treats as "ask fresh."
    op.add_column('customers', sa.Column('last_payment_method', sa.String(length=16), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('customers', 'last_payment_method')
