"""encrypt customer whatsapp number and address pii

Revision ID: 1056afac7508
Revises: c0ca5d2bcc50
Create Date: 2026-09-07 14:00:51.201267

Encrypts Customer.whatsapp_number and Address.line1/line2/landmark/city/
pincode at rest with the app's existing Fernet cipher (shared/encryption.py
-- already used for WhatsApp/Razorpay credentials, now reused for customer
PII rather than standing up a second scheme). See
customers/domain/models.py's FernetEncryptedString for why this is done
transparently at the column-type level rather than with explicit
encrypt()/decrypt() calls in the repository (this codebase's usual
convention for encrypted credential columns): Customer/Address rows are
loaded from several other places in the app via a plain SQLAlchemy
relationship (Order.customer, Order.delivery_address, Appointment.customer),
bypassing CustomerRepository/AddressRepository entirely, so decryption must
happen for every load path, not just this module's own repository calls.

whatsapp_number itself is non-deterministic ciphertext once encrypted (a
fresh random IV every time, even for the same plaintext), so it can no
longer serve as an exact-match lookup/uniqueness key -- a new deterministic
column, whatsapp_number_lookup_hash (HMAC-SHA256 of the canonicalized
number, keyed by secrets_encryption_key), takes over that role, and the
unique constraint moves from (merchant_id, whatsapp_number) to
(merchant_id, whatsapp_number_lookup_hash). Address fields are never
queried by value, so they get no lookup-hash companion.

This is a data migration, not just a schema change: existing plaintext
rows are encrypted (and their lookup hash backfilled) in place, in the
same migration, using Python (Fernet/HMAC have no SQL-level equivalent),
via op.get_bind() -- SECRETS_ENCRYPTION_KEY must be set in the environment
this migration runs in, same requirement shared/encryption.py already has
at request time. A single pass (no batching) is deliberate: this
migration runs once, on a customers table sized for a pilot-phase
restaurant deployment, not a high-volume table needing chunked backfills.
"""
import hashlib
import hmac
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from shared.config import get_settings
from shared.encryption import decrypt, encrypt

# revision identifiers, used by Alembic.
revision: str = '1056afac7508'
down_revision: Union[str, Sequence[str], None] = 'c0ca5d2bcc50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _lookup_hash(whatsapp_number: str) -> str:
    """Same HMAC construction as customers/adapters/repository.py's
    _whatsapp_number_lookup_hash -- duplicated here (rather than imported)
    because a migration must stay correct as of the moment it was written,
    independent of how that function evolves later; see e.g.
    badd83266c3c's ROW_NUMBER() backfill for the same "migrations are
    frozen in time" reasoning applied via raw SQL instead of Python."""
    key = get_settings().secrets_encryption_key.encode("utf-8")
    return hmac.new(key, whatsapp_number.encode("utf-8"), hashlib.sha256).hexdigest()


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    # 1. Add the new nullable hash column, and widen the columns that are
    # about to hold Fernet ciphertext instead of their original bounded
    # plaintext -- a Fernet token is meaningfully longer than a phone
    # number or an address line, and grows with plaintext length, so a
    # fixed VARCHAR bound no longer fits. Nullable/unconstrained for now;
    # the backfill below fills every row before anything is tightened.
    op.add_column(
        'customers',
        sa.Column('whatsapp_number_lookup_hash', sa.String(length=64), nullable=True),
    )
    op.alter_column(
        'customers', 'whatsapp_number',
        existing_type=sa.String(length=32), type_=sa.Text(), existing_nullable=False,
    )
    op.alter_column(
        'addresses', 'line1',
        existing_type=sa.String(length=255), type_=sa.Text(), existing_nullable=False,
    )
    op.alter_column(
        'addresses', 'line2',
        existing_type=sa.String(length=255), type_=sa.Text(), existing_nullable=True,
    )
    op.alter_column(
        'addresses', 'landmark',
        existing_type=sa.String(length=255), type_=sa.Text(), existing_nullable=True,
    )
    op.alter_column(
        'addresses', 'city',
        existing_type=sa.String(length=128), type_=sa.Text(), existing_nullable=False,
    )
    op.alter_column(
        'addresses', 'pincode',
        existing_type=sa.String(length=16), type_=sa.Text(), existing_nullable=False,
    )

    # 2. Backfill: encrypt every existing plaintext value in place, and
    # compute whatsapp_number_lookup_hash from the (still-plaintext, at
    # read time) value. Values are read once, then written back
    # per-row -- avoids ever comparing/updating with a mismatched
    # already-encrypted value if this migration were re-run partway (it
    # isn't idempotent against a partial failure either way, matching this
    # codebase's other hand-written data migrations, e.g. badd83266c3c).
    customer_rows = bind.execute(
        sa.text("SELECT customer_id, whatsapp_number FROM customers")
    ).fetchall()
    for customer_id, whatsapp_number in customer_rows:
        bind.execute(
            sa.text(
                "UPDATE customers "
                "SET whatsapp_number = :enc, whatsapp_number_lookup_hash = :hash "
                "WHERE customer_id = :id"
            ),
            {
                "enc": encrypt(whatsapp_number),
                "hash": _lookup_hash(whatsapp_number),
                "id": customer_id,
            },
        )

    address_rows = bind.execute(
        sa.text("SELECT address_id, line1, line2, landmark, city, pincode FROM addresses")
    ).fetchall()
    for address_id, line1, line2, landmark, city, pincode in address_rows:
        bind.execute(
            sa.text(
                "UPDATE addresses "
                "SET line1 = :line1, line2 = :line2, landmark = :landmark, "
                "    city = :city, pincode = :pincode "
                "WHERE address_id = :id"
            ),
            {
                "line1": encrypt(line1),
                "line2": encrypt(line2) if line2 is not None else None,
                "landmark": encrypt(landmark) if landmark is not None else None,
                "city": encrypt(city),
                "pincode": encrypt(pincode),
                "id": address_id,
            },
        )

    # 3. Constraints move AFTER the backfill: every row now has a hash, so
    # NOT NULL + the new unique constraint can be applied safely, and the
    # old value-based constraint (meaningless against ciphertext -- see
    # module docstring) is dropped.
    op.alter_column(
        'customers', 'whatsapp_number_lookup_hash',
        existing_type=sa.String(length=64), nullable=False,
    )
    op.drop_constraint('uq_customers_merchant_whatsapp', 'customers', type_='unique')
    op.create_unique_constraint(
        'uq_customers_merchant_whatsapp_hash',
        'customers',
        ['merchant_id', 'whatsapp_number_lookup_hash'],
    )
    op.create_index(
        op.f('ix_customers_whatsapp_number_lookup_hash'),
        'customers',
        ['whatsapp_number_lookup_hash'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema. Best-effort: decrypts data back to plaintext and
    restores the original value-based constraint/column widths."""
    bind = op.get_bind()

    op.drop_index(op.f('ix_customers_whatsapp_number_lookup_hash'), table_name='customers')
    op.drop_constraint('uq_customers_merchant_whatsapp_hash', 'customers', type_='unique')

    customer_rows = bind.execute(
        sa.text("SELECT customer_id, whatsapp_number FROM customers")
    ).fetchall()
    for customer_id, whatsapp_number in customer_rows:
        bind.execute(
            sa.text("UPDATE customers SET whatsapp_number = :dec WHERE customer_id = :id"),
            {"dec": decrypt(whatsapp_number), "id": customer_id},
        )

    address_rows = bind.execute(
        sa.text("SELECT address_id, line1, line2, landmark, city, pincode FROM addresses")
    ).fetchall()
    for address_id, line1, line2, landmark, city, pincode in address_rows:
        bind.execute(
            sa.text(
                "UPDATE addresses "
                "SET line1 = :line1, line2 = :line2, landmark = :landmark, "
                "    city = :city, pincode = :pincode "
                "WHERE address_id = :id"
            ),
            {
                "line1": decrypt(line1),
                "line2": decrypt(line2) if line2 is not None else None,
                "landmark": decrypt(landmark) if landmark is not None else None,
                "city": decrypt(city),
                "pincode": decrypt(pincode),
                "id": address_id,
            },
        )

    op.create_unique_constraint(
        'uq_customers_merchant_whatsapp', 'customers', ['merchant_id', 'whatsapp_number']
    )
    op.drop_column('customers', 'whatsapp_number_lookup_hash')

    op.alter_column(
        'customers', 'whatsapp_number',
        existing_type=sa.Text(), type_=sa.String(length=32), existing_nullable=False,
    )
    op.alter_column(
        'addresses', 'line1',
        existing_type=sa.Text(), type_=sa.String(length=255), existing_nullable=False,
    )
    op.alter_column(
        'addresses', 'line2',
        existing_type=sa.Text(), type_=sa.String(length=255), existing_nullable=True,
    )
    op.alter_column(
        'addresses', 'landmark',
        existing_type=sa.Text(), type_=sa.String(length=255), existing_nullable=True,
    )
    op.alter_column(
        'addresses', 'city',
        existing_type=sa.Text(), type_=sa.String(length=128), existing_nullable=False,
    )
    op.alter_column(
        'addresses', 'pincode',
        existing_type=sa.Text(), type_=sa.String(length=16), existing_nullable=False,
    )
