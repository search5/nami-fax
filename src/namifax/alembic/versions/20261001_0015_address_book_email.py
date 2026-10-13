"""create AddressBookEmail

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-01

Only creates the table when the legacy SQLite schema code has not already done so.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("AddressBookEmail"):
        return
    op.create_table(
        "AddressBookEmail",
        sa.Column("abookemail_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("abook_id", sa.Integer(), nullable=True),
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("abookemail_id", name=op.f("pk_AddressBookEmail")),
    )
    op.create_index(op.f("ix_AddressBookEmail_contact_email"), "AddressBookEmail", ["contact_email"], unique=False)


def downgrade():
    op.drop_table("AddressBookEmail")
