"""drop merchant appointment_booking_enabled toggle

Revision ID: 0593f7b92f82
Revises: 560ee56f245c
Create Date: 2026-09-02 23:20:41.224323

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0593f7b92f82'
down_revision: Union[str, Sequence[str], None] = '560ee56f245c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    MULTI_VERTICAL_PLAN.md Phase M5: retires the additive opt-in toggle
    now that Merchant.vertical (Phase M1) is the sole gate everywhere that
    used to read this column -- shared/scheduler.py's reminder scan,
    appointment_flow/api/router.py's public booking-webview gate, the
    WhatsApp conversation handler's menu, and the Settings-page toggle UI
    all switched over in earlier phases, so no code reads this column by
    the time this migration runs.
    """
    op.drop_column('merchants', 'appointment_booking_enabled')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'merchants',
        sa.Column(
            'appointment_booking_enabled',
            sa.BOOLEAN(),
            server_default=sa.false(),
            autoincrement=False,
            nullable=False,
        ),
    )
