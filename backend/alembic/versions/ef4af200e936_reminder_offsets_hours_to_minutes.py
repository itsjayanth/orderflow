"""reminder offsets: hours to minutes, default 60/30

Revision ID: ef4af200e936
Revises: 215b9cb77f05
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef4af200e936'
down_revision: Union[str, Sequence[str], None] = '215b9cb77f05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename both hour-granularity reminder-offset columns to
    minute-granularity, converting existing stored values (x hours -> x*60
    minutes) so no merchant's configured reminder timing silently changes
    meaning. Minute granularity is required for the product spec's
    30-minute-before reminder, which a whole-hour offset can't represent
    (see appointments/domain/models.py's AppointmentReminder and
    identity/domain/models.py's Merchant.reminder_offsets_minutes)."""
    op.alter_column(
        'merchants', 'reminder_offsets_hours', new_column_name='reminder_offsets_minutes'
    )
    # JSON array of integers -- multiply each element by 60 in place via
    # jsonb_agg over jsonb_array_elements, then cast back to json (the
    # column's declared type).
    op.execute(
        """
        UPDATE merchants
        SET reminder_offsets_minutes = (
            SELECT COALESCE(jsonb_agg((elem.value::int) * 60), '[]'::jsonb)
            FROM jsonb_array_elements(reminder_offsets_minutes::jsonb) AS elem
        )::json
        """
    )
    op.alter_column(
        'merchants',
        'reminder_offsets_minutes',
        server_default='[60, 30]',
    )
    op.alter_column('merchants', 'reminder_offsets_minutes', server_default=None)

    op.alter_column(
        'appointment_reminders', 'offset_hours', new_column_name='offset_minutes'
    )
    op.execute('UPDATE appointment_reminders SET offset_minutes = offset_minutes * 60')
    # Cosmetic only (Postgres doesn't rename a constraint when its column
    # is renamed) -- keeps \d output from referencing a column name that
    # no longer exists.
    op.execute(
        'ALTER TABLE appointment_reminders '
        'RENAME CONSTRAINT appointment_reminders_appointment_id_offset_hours_key '
        'TO appointment_reminders_appointment_id_offset_minutes_key'
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE merchants
        SET reminder_offsets_minutes = (
            SELECT COALESCE(jsonb_agg((elem.value::int) / 60), '[]'::jsonb)
            FROM jsonb_array_elements(reminder_offsets_minutes::jsonb) AS elem
        )::json
        """
    )
    op.alter_column(
        'merchants', 'reminder_offsets_minutes', new_column_name='reminder_offsets_hours'
    )

    op.execute(
        'ALTER TABLE appointment_reminders '
        'RENAME CONSTRAINT appointment_reminders_appointment_id_offset_minutes_key '
        'TO appointment_reminders_appointment_id_offset_hours_key'
    )
    op.execute('UPDATE appointment_reminders SET offset_minutes = offset_minutes / 60')
    op.alter_column(
        'appointment_reminders', 'offset_minutes', new_column_name='offset_hours'
    )
