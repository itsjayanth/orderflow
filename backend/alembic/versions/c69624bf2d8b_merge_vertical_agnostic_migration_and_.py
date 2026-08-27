"""merge vertical-agnostic migration and FAQ/appointment-booking heads

Revision ID: c69624bf2d8b
Revises: 70e512b414d0, ecd2e54f8655
Create Date: 2026-08-27 01:15:56.375302

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c69624bf2d8b'
down_revision: Union[str, Sequence[str], None] = ('70e512b414d0', 'ecd2e54f8655')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
