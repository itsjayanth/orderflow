"""add header_filename to message_templates

Revision ID: a696b23f8aeb
Revises: 8a0d1565cf9b
Create Date: 2026-09-04 02:59:20.677302

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a696b23f8aeb'
down_revision: Union[str, Sequence[str], None] = '8a0d1565cf9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Broadcast-messaging Phase 16: Meta's required display filename for
    a DOCUMENT template header -- see campaigns/domain/models.py's
    MessageTemplate.header_filename docstring."""
    op.add_column(
        'message_templates', sa.Column('header_filename', sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('message_templates', 'header_filename')
