"""add image_url to menu items

Revision ID: 510663d692cb
Revises: d0bb34e641c6
Create Date: 2026-08-08 11:34:22.389532

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '510663d692cb'
down_revision: Union[str, Sequence[str], None] = 'd0bb34e641c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable, no backfill -- NULL is a valid "no image set" state, unlike
    # item_number's migration (d0bb34e641c6) which had to backfill existing
    # rows before going NOT NULL.
    op.add_column('menu_items', sa.Column('image_url', sa.String(length=2048), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('menu_items', 'image_url')
