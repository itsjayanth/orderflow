"""add faq_items

Revision ID: ecd2e54f8655
Revises: 50fa02971d49
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ecd2e54f8655'
down_revision: Union[str, Sequence[str], None] = '50fa02971d49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'faq_items',
        sa.Column('faq_item_id', sa.Uuid(), nullable=False),
        sa.Column('merchant_id', sa.Uuid(), nullable=False),
        sa.Column('question_text', sa.String(length=500), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=False),
        sa.Column('keywords', postgresql.ARRAY(sa.String(length=255)), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.merchant_id'], ),
        sa.PrimaryKeyConstraint('faq_item_id'),
    )
    op.create_index(op.f('ix_faq_items_merchant_id'), 'faq_items', ['merchant_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_faq_items_merchant_id'), table_name='faq_items')
    op.drop_table('faq_items')
