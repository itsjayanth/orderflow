"""add restaurant_enabled and appointment_enabled to merchants

Revision ID: e641ff0754e6
Revises: 0593f7b92f82
Create Date: 2026-09-03 09:15:57.225907

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e641ff0754e6'
down_revision: Union[str, Sequence[str], None] = '0593f7b92f82'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # VERTICAL_TOGGLE_PLAN.md Phase T1: replaces the single mutually-exclusive
    # `vertical` enum column (Phase 10) with two independent booleans, so a
    # merchant can have either or both verticals on. server_default=false
    # satisfies the NOT NULL constraint for existing rows during the
    # add_column itself; the backfill UPDATE below then sets the correct
    # value from each row's old `vertical` before it's dropped.
    op.add_column(
        'merchants',
        sa.Column('restaurant_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'merchants',
        sa.Column('appointment_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # A merchant whose `vertical` was still NULL (registered but hasn't
    # answered the onboarding wizard's first step yet) gets both flags
    # False via COALESCE -- the same transient "not yet selected" state the
    # nullable `vertical` column used to represent, not a violation of the
    # restaurant_enabled/appointment_enabled invariant the application layer
    # enforces from here on (that invariant only applies once a merchant has
    # made a choice at all).
    op.execute(
        """
        UPDATE merchants
        SET restaurant_enabled = COALESCE(vertical = 'restaurant', false),
            appointment_enabled = COALESCE(vertical = 'appointment', false)
        """
    )

    op.alter_column('merchants', 'restaurant_enabled', server_default=None)
    op.alter_column('merchants', 'appointment_enabled', server_default=None)

    op.drop_column('merchants', 'vertical')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('merchants', sa.Column('vertical', sa.String(length=16), nullable=True))

    # Best-effort reverse mapping -- a merchant with both flags True (only
    # reachable going forward, never possible under the old exclusive
    # `vertical` column) collapses to 'restaurant' on downgrade, since the
    # old column can't represent "both."
    op.execute(
        """
        UPDATE merchants
        SET vertical = CASE
            WHEN restaurant_enabled THEN 'restaurant'
            WHEN appointment_enabled THEN 'appointment'
            ELSE NULL
        END
        """
    )

    op.drop_column('merchants', 'appointment_enabled')
    op.drop_column('merchants', 'restaurant_enabled')
