"""add message_templates

Revision ID: 1e324010597b
Revises: 743ed9498d8b
Create Date: 2026-09-04 02:15:07.345371

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e324010597b'
down_revision: Union[str, Sequence[str], None] = '743ed9498d8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Broadcast-messaging Phase 13: a merchant's own WhatsApp templates,
    submitted for real via Meta's message_templates API -- see
    campaigns/domain/models.py's MessageTemplate docstring."""
    op.create_table(
        'message_templates',
        sa.Column('template_id', sa.Uuid(), nullable=False),
        sa.Column('merchant_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=512), nullable=False),
        sa.Column('category', sa.String(length=16), nullable=False),
        sa.Column('language_code', sa.String(length=16), nullable=False),
        sa.Column('header_type', sa.String(length=16), nullable=False),
        sa.Column('header_text', sa.String(length=60), nullable=True),
        sa.Column('header_media_handle', sa.String(length=512), nullable=True),
        sa.Column('body_text', sa.Text(), nullable=False),
        sa.Column('body_variable_count', sa.Integer(), nullable=False),
        sa.Column('footer_text', sa.String(length=60), nullable=True),
        sa.Column('buttons', sa.JSON(), nullable=False),
        sa.Column('meta_template_id', sa.String(length=255), nullable=True),
        sa.Column('meta_approval_status', sa.String(length=16), nullable=False),
        sa.Column('meta_rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['merchant_id'], ['merchants.merchant_id']),
        sa.PrimaryKeyConstraint('template_id'),
    )
    op.create_index(
        op.f('ix_message_templates_merchant_id'), 'message_templates', ['merchant_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_message_templates_merchant_id'), table_name='message_templates')
    op.drop_table('message_templates')
