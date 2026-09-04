"""add campaigns, campaign_recipients, messaging tier

Revision ID: 8a0d1565cf9b
Revises: 1e324010597b
Create Date: 2026-09-04 02:33:12.682858

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a0d1565cf9b'
down_revision: Union[str, Sequence[str], None] = '1e324010597b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Broadcast-messaging Phase 14: the campaign entity, its per-recipient
    send ledger, and the admin-settable messaging-tier field -- see
    campaigns/domain/models.py's Campaign/CampaignRecipient docstrings and
    onboarding/domain/models.py's messaging_tier_daily_limit docstring.
    server_default='250' on messaging_tier_daily_limit satisfies NOT NULL
    for every existing whatsapp_business_accounts row (Meta's own default
    "Limited Access" tier, matching the Python-side default going forward)."""
    op.create_table(
        'campaigns',
        sa.Column('campaign_id', sa.Uuid(), nullable=False),
        sa.Column('merchant_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('template_id', sa.Uuid(), nullable=False),
        sa.Column('audience_filter', sa.JSON(), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('created_by', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.merchant_id']),
        sa.ForeignKeyConstraint(['template_id'], ['message_templates.template_id']),
        sa.PrimaryKeyConstraint('campaign_id'),
    )
    op.create_index(op.f('ix_campaigns_merchant_id'), 'campaigns', ['merchant_id'], unique=False)
    op.create_table(
        'campaign_recipients',
        sa.Column('recipient_id', sa.Uuid(), nullable=False),
        sa.Column('campaign_id', sa.Uuid(), nullable=False),
        sa.Column('customer_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('whatsapp_message_id', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.campaign_id']),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
        sa.PrimaryKeyConstraint('recipient_id'),
        sa.UniqueConstraint('campaign_id', 'customer_id'),
    )
    op.create_index(
        op.f('ix_campaign_recipients_campaign_id'), 'campaign_recipients', ['campaign_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_campaign_recipients_customer_id'), 'campaign_recipients', ['customer_id'],
        unique=False,
    )
    op.add_column(
        'whatsapp_business_accounts',
        sa.Column(
            'messaging_tier_daily_limit', sa.Integer(), nullable=False, server_default='250'
        ),
    )
    op.alter_column('whatsapp_business_accounts', 'messaging_tier_daily_limit', server_default=None)


def downgrade() -> None:
    op.drop_column('whatsapp_business_accounts', 'messaging_tier_daily_limit')
    op.drop_index(op.f('ix_campaign_recipients_customer_id'), table_name='campaign_recipients')
    op.drop_index(op.f('ix_campaign_recipients_campaign_id'), table_name='campaign_recipients')
    op.drop_table('campaign_recipients')
    op.drop_index(op.f('ix_campaigns_merchant_id'), table_name='campaigns')
    op.drop_table('campaigns')
