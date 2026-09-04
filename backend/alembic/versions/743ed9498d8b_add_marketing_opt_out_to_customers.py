"""add marketing opt-out to customers

Revision ID: 743ed9498d8b
Revises: 151cfda0da74
Create Date: 2026-09-04 01:58:33.183306

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '743ed9498d8b'
down_revision: Union[str, Sequence[str], None] = '151cfda0da74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Broadcast-messaging Phase 12: WhatsApp Business Platform policy
    requires honoring STOP/opt-out for MARKETING-category sends -- see
    customers/domain/models.py's Customer.marketing_opt_out docstring.
    server_default='false' satisfies NOT NULL for every existing row
    (nobody has opted out before this column existed)."""
    op.add_column(
        'customers',
        sa.Column(
            'marketing_opt_out', sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        'customers', sa.Column('marketing_opt_out_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.alter_column('customers', 'marketing_opt_out', server_default=None)


def downgrade() -> None:
    op.drop_column('customers', 'marketing_opt_out_at')
    op.drop_column('customers', 'marketing_opt_out')
