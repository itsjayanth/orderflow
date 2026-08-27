"""generalize merchant business profile fields

Revision ID: 74f76cb509a0
Revises: b14b80115eb8
Create Date: 2026-08-26 18:40:02.530836

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '74f76cb509a0'
down_revision: Union[str, Sequence[str], None] = 'b14b80115eb8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Straight renames (table/column), not additive-then-swap -- preserves
    every existing row (including the real Varkey's merchant data, see
    docs/generic-platform-migration.md) since a RENAME isn't a destructive
    drop, and this app's pre-deploy migration gate means no old-code reader
    is ever running concurrently against the old names.
    """
    op.alter_column('merchants', 'kitchen_address_line1', new_column_name='business_address_line1')
    op.alter_column('merchants', 'kitchen_address_line2', new_column_name='business_address_line2')
    op.alter_column('merchants', 'kitchen_city', new_column_name='business_city')
    op.alter_column('merchants', 'kitchen_pincode', new_column_name='business_pincode')
    op.alter_column('merchants', 'cuisine_type', new_column_name='business_category')
    op.alter_column('merchants', 'fssai_license_no', new_column_name='license_no')


def downgrade() -> None:
    """Downgrade schema -- exact reverse of upgrade()."""
    op.alter_column('merchants', 'license_no', new_column_name='fssai_license_no')
    op.alter_column('merchants', 'business_category', new_column_name='cuisine_type')
    op.alter_column('merchants', 'business_pincode', new_column_name='kitchen_pincode')
    op.alter_column('merchants', 'business_city', new_column_name='kitchen_city')
    op.alter_column('merchants', 'business_address_line2', new_column_name='kitchen_address_line2')
    op.alter_column('merchants', 'business_address_line1', new_column_name='kitchen_address_line1')
