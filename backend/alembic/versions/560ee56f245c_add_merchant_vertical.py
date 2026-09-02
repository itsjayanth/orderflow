"""add merchant vertical

Revision ID: 560ee56f245c
Revises: 01d592a90b44
Create Date: 2026-09-02 22:47:41.547963

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '560ee56f245c'
down_revision: Union[str, Sequence[str], None] = '01d592a90b44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('merchants', sa.Column('vertical', sa.String(length=16), nullable=True))

    # MULTI_VERTICAL_PLAN.md Phase M1: backfill every existing merchant so
    # none is left with vertical=NULL post-migration -- preserves today's
    # behavior for a merchant who already opted into the additive
    # appointment_booking_enabled toggle (they become the 'appointment'
    # vertical) while every other existing merchant defaults to
    # 'restaurant', matching what every merchant on this platform has been
    # until now. New merchants set this explicitly via the onboarding
    # wizard's new first step instead of relying on this default.
    op.execute(
        """
        UPDATE merchants
        SET vertical = CASE WHEN appointment_booking_enabled THEN 'appointment' ELSE 'restaurant' END
        WHERE vertical IS NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('merchants', 'vertical')
