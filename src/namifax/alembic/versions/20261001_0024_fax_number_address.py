"""add the street address, zip and city of a fax number (the original AvantFAX has them since 3.3.4)

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

_COLUMNS = (("to_address", 50), ("to_zip", 16), ("to_city", 50))


def upgrade():
    present = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("AddressBookFAX")}
    for name, length in _COLUMNS:
        if name not in present:
            op.add_column("AddressBookFAX", sa.Column(name, sa.String(length=length), nullable=False, server_default=""))


def downgrade():
    with op.batch_alter_table("AddressBookFAX") as batch:
        for name, _ in _COLUMNS:
            batch.drop_column(name)
