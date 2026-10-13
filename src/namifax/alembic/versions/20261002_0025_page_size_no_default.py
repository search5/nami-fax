"""no stored page size for a new account: NULL means the configured default (the original's columns have no default)

Rows that already hold a value keep it: a size the user chose cannot be told from the old default of 10.

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

_COLUMNS = ("faxperpageinbox", "faxperpagearchive")


def upgrade():
    with op.batch_alter_table("UserAccount") as batch:
        for name in _COLUMNS:
            batch.alter_column(name, existing_type=sa.Integer(), existing_nullable=True, server_default=None)


def downgrade():
    with op.batch_alter_table("UserAccount") as batch:
        for name in _COLUMNS:
            batch.alter_column(name, existing_type=sa.Integer(), existing_nullable=True, server_default="10")
