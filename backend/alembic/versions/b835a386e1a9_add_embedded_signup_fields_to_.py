"""add embedded signup fields to whatsapp_business_accounts

Revision ID: b835a386e1a9
Revises: 50fa02971d49
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b835a386e1a9'
down_revision: Union[str, Sequence[str], None] = '50fa02971d49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'whatsapp_business_accounts',
        sa.Column(
            'connection_method',
            sa.String(length=32),
            nullable=False,
            server_default='manual',
        ),
    )
    op.add_column(
        'whatsapp_business_accounts',
        sa.Column('two_step_pin_encrypted', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('whatsapp_business_accounts', 'two_step_pin_encrypted')
    op.drop_column('whatsapp_business_accounts', 'connection_method')
