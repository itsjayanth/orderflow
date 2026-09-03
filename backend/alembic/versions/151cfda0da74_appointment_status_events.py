"""appointment status events (audit log)

Revision ID: 151cfda0da74
Revises: ef4af200e936
Create Date: 2026-09-03 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '151cfda0da74'
down_revision: Union[str, Sequence[str], None] = 'ef4af200e936'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Append-only audit trail for an appointment's whole lifecycle (Task
    5 of the appointment scheduling plan) -- see
    appointments/domain/models.py's AppointmentStatusEvent docstring for
    what each nullable column is populated for, per event_type."""
    op.create_table(
        'appointment_status_events',
        sa.Column('status_event_id', sa.Uuid(), nullable=False),
        sa.Column('appointment_id', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(length=32), nullable=False),
        sa.Column('from_status', sa.String(length=32), nullable=True),
        sa.Column('to_status', sa.String(length=32), nullable=True),
        sa.Column('from_appointment_date', sa.Date(), nullable=True),
        sa.Column('from_start_time', sa.Time(), nullable=True),
        sa.Column('to_appointment_date', sa.Date(), nullable=True),
        sa.Column('to_start_time', sa.Time(), nullable=True),
        sa.Column('offset_minutes', sa.Integer(), nullable=True),
        sa.Column('changed_by', sa.String(length=64), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.appointment_id']),
        sa.PrimaryKeyConstraint('status_event_id'),
    )
    op.create_index(
        op.f('ix_appointment_status_events_appointment_id'),
        'appointment_status_events',
        ['appointment_id'],
        unique=False,
    )

    # Backfill a "requested" event for every appointment that already
    # exists (this table is new, so history before now would otherwise
    # start blank) -- best-effort reconstruction from Appointment's own
    # columns; a pre-existing row has no way to know its *originally*
    # requested slot if it was ever rescheduled before this migration, so
    # this backfills the *current* slot for those, same limitation any
    # audit log added after the fact has for data it didn't watch happen.
    op.execute(
        """
        INSERT INTO appointment_status_events
            (status_event_id, appointment_id, event_type, to_status,
             to_appointment_date, to_start_time, changed_by, changed_at)
        SELECT gen_random_uuid(), appointment_id, 'requested', 'requested',
               appointment_date, start_time, created_via, requested_at
        FROM appointments
        """
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_appointment_status_events_appointment_id'),
        table_name='appointment_status_events',
    )
    op.drop_table('appointment_status_events')
