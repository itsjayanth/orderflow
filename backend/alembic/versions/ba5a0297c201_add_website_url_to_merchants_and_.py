"""add website_url to merchants and website_link_clicks table

Revision ID: ba5a0297c201
Revises: e641ff0754e6
Create Date: 2026-09-03 10:06:55.990512

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba5a0297c201'
down_revision: Union[str, Sequence[str], None] = 'e641ff0754e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('merchants', sa.Column('website_url', sa.String(length=2048), nullable=True))

    op.create_table(
        'website_link_clicks',
        sa.Column('click_id', sa.Uuid(), nullable=False),
        sa.Column('merchant_id', sa.Uuid(), nullable=False),
        sa.Column('clicked_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.merchant_id']),
        sa.PrimaryKeyConstraint('click_id'),
    )
    op.create_index(
        op.f('ix_website_link_clicks_merchant_id'),
        'website_link_clicks',
        ['merchant_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_website_link_clicks_clicked_at'),
        'website_link_clicks',
        ['clicked_at'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_website_link_clicks_clicked_at'), table_name='website_link_clicks')
    op.drop_index(op.f('ix_website_link_clicks_merchant_id'), table_name='website_link_clicks')
    op.drop_table('website_link_clicks')

    op.drop_column('merchants', 'website_url')
