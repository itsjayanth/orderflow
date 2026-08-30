"""add registration_pin_encrypted to whatsapp_business_accounts

Revision ID: 35dc91b13ba6
Revises: f2bfa36941b5
Create Date: 2026-08-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35dc91b13ba6'
down_revision: Union[str, Sequence[str], None] = 'f2bfa36941b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'whatsapp_business_accounts',
        sa.Column('registration_pin_encrypted', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('whatsapp_business_accounts', 'registration_pin_encrypted')
