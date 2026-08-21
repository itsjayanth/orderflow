"""add customer email and order notes

Revision ID: 50fa02971d49
Revises: c01e9485d53e
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50fa02971d49'
down_revision: Union[str, Sequence[str], None] = 'c01e9485d53e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('customers', sa.Column('email', sa.String(length=255), nullable=True))
    op.add_column('orders', sa.Column('notes', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('orders', 'notes')
    op.drop_column('customers', 'email')
