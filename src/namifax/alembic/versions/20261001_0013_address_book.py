"""create AddressBook

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-01

Only creates the table when the legacy SQLite schema code has not already done so.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("AddressBook"):
        return
    op.create_table(
        "AddressBook",
        sa.Column("abook_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("faxtype", sa.String(length=32), nullable=True),
        sa.Column("faxnum", sa.String(length=64), nullable=True),
        sa.Column("phonenum", sa.String(length=64), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("state", sa.String(length=64), nullable=True),
        sa.Column("zip", sa.String(length=32), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("abook_id", name=op.f("pk_AddressBook")),
    )


def downgrade():
    op.drop_table("AddressBook")
