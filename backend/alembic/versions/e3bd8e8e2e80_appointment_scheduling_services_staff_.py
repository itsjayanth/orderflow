"""appointment scheduling: services, staff, availability, overlap prevention, payments

Revision ID: e3bd8e8e2e80
Revises: 35dc91b13ba6
Create Date: 2026-09-02 00:06:14.096946

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e3bd8e8e2e80'
down_revision: Union[str, Sequence[str], None] = '35dc91b13ba6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Matches appointment_flow/domain/booking.py's _DEFAULT_DURATION_MINUTES --
# used only to backfill end_time for any appointment rows that predate this
# migration (nothing at request time falls back to a hardcoded literal
# instead of importing that constant, this is a one-off backfill value).
_DEFAULT_DURATION_MINUTES = 30


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('appointment_services',
    sa.Column('service_id', sa.Uuid(), nullable=False),
    sa.Column('merchant_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('duration_minutes', sa.Integer(), nullable=False),
    sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.merchant_id'], ),
    sa.PrimaryKeyConstraint('service_id')
    )
    op.create_index(op.f('ix_appointment_services_merchant_id'), 'appointment_services', ['merchant_id'], unique=False)

    op.create_table('staff_resources',
    sa.Column('staff_id', sa.Uuid(), nullable=False),
    sa.Column('merchant_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.merchant_id'], ),
    sa.PrimaryKeyConstraint('staff_id')
    )
    op.create_index(op.f('ix_staff_resources_merchant_id'), 'staff_resources', ['merchant_id'], unique=False)

    op.create_table('merchant_availability',
    sa.Column('availability_id', sa.Uuid(), nullable=False),
    sa.Column('merchant_id', sa.Uuid(), nullable=False),
    sa.Column('staff_id', sa.Uuid(), nullable=True),
    sa.Column('day_of_week', sa.Integer(), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=False),
    sa.Column('end_time', sa.Time(), nullable=False),
    sa.Column('slot_duration_minutes', sa.Integer(), nullable=False),
    sa.Column('buffer_minutes', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.merchant_id'], ),
    sa.ForeignKeyConstraint(['staff_id'], ['staff_resources.staff_id'], ),
    sa.PrimaryKeyConstraint('availability_id')
    )
    op.create_index(op.f('ix_merchant_availability_merchant_id'), 'merchant_availability', ['merchant_id'], unique=False)

    # Rename, not drop+add -- autogenerate saw this as "remove
    # appointment_time / add start_time" (two different columns), which
    # would silently NULL/drop every existing appointment's time. A plain
    # rename preserves the data and needs no backfill for this column.
    op.alter_column('appointments', 'appointment_time', new_column_name='start_time')

    # end_time has no natural per-row source -- backfill any pre-existing
    # appointment rows to start_time + 30 minutes (this migration's own
    # _DEFAULT_DURATION_MINUTES, matching the app-level default in
    # appointment_flow/domain/booking.py) before enforcing NOT NULL.
    op.add_column('appointments', sa.Column('end_time', sa.Time(), nullable=True))
    op.execute(
        f"UPDATE appointments SET end_time = start_time + INTERVAL "
        f"'{_DEFAULT_DURATION_MINUTES} minutes' WHERE end_time IS NULL"
    )
    op.alter_column('appointments', 'end_time', nullable=False)

    op.add_column('appointments', sa.Column('service_id', sa.Uuid(), nullable=True))
    op.add_column('appointments', sa.Column('staff_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_appointments_service_id_appointment_services', 'appointments', 'appointment_services', ['service_id'], ['service_id'])
    op.create_foreign_key('fk_appointments_staff_id_staff_resources', 'appointments', 'staff_resources', ['staff_id'], ['staff_id'])

    # created_via/payment_status: server_default backfills existing rows,
    # then gets dropped so new rows rely on the Python-side model defaults
    # going forward -- same two-step pattern as
    # 3e2e2914b3be_add_appointment_booking.py's appointment_booking_enabled
    # column.
    op.add_column('appointments', sa.Column('created_via', sa.String(length=16), nullable=False, server_default='browser'))
    op.alter_column('appointments', 'created_via', server_default=None)
    op.add_column('appointments', sa.Column('payment_status', sa.String(length=16), nullable=False, server_default='not_required'))
    op.alter_column('appointments', 'payment_status', server_default=None)

    op.add_column('merchants', sa.Column('timezone', sa.String(length=64), nullable=False, server_default='Asia/Kolkata'))
    op.alter_column('merchants', 'timezone', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('merchants', 'timezone')
    op.drop_column('appointments', 'payment_status')
    op.drop_column('appointments', 'created_via')
    op.drop_constraint('fk_appointments_staff_id_staff_resources', 'appointments', type_='foreignkey')
    op.drop_constraint('fk_appointments_service_id_appointment_services', 'appointments', type_='foreignkey')
    op.drop_column('appointments', 'staff_id')
    op.drop_column('appointments', 'service_id')
    op.drop_column('appointments', 'end_time')
    op.alter_column('appointments', 'start_time', new_column_name='appointment_time')
    op.drop_index(op.f('ix_merchant_availability_merchant_id'), table_name='merchant_availability')
    op.drop_table('merchant_availability')
    op.drop_index(op.f('ix_staff_resources_merchant_id'), table_name='staff_resources')
    op.drop_table('staff_resources')
    op.drop_index(op.f('ix_appointment_services_merchant_id'), table_name='appointment_services')
    op.drop_table('appointment_services')
