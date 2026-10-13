"""create AddressBookFAX

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-01

Only creates the table when the legacy SQLite schema code has not already done so.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("AddressBookFAX"):
        return
    op.create_table(
        "AddressBookFAX",
        sa.Column("abookfax_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("abook_id", sa.Integer(), nullable=True),
        sa.Column("faxnumber", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("to_person", sa.String(length=255), nullable=True),
        sa.Column("to_location", sa.String(length=255), nullable=True),
        sa.Column("to_voicenumber", sa.String(length=255), nullable=True),
        sa.Column("faxcatid", sa.Integer(), nullable=True),
        sa.Column("faxfrom", sa.Integer(), server_default="0", nullable=True),
        sa.Column("faxto", sa.Integer(), server_default="0", nullable=True),
        sa.Column("printer", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("abookfax_id", name=op.f("pk_AddressBookFAX")),
    )
    op.create_index(op.f("ix_AddressBookFAX_abook_id"), "AddressBookFAX", ["abook_id"], unique=False)
    op.create_index(op.f("ix_AddressBookFAX_faxnumber"), "AddressBookFAX", ["faxnumber"], unique=False)


def downgrade():
    op.drop_table("AddressBookFAX")
