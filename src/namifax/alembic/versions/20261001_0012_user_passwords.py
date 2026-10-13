"""create UserPasswords

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-01

Only creates the table when the legacy SQLite schema code has not already done so.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("UserPasswords"):
        return
    op.create_table(
        "UserPasswords",
        sa.Column("upid", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", sa.Integer(), nullable=False),
        sa.Column("pwdhash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("upid", name=op.f("pk_UserPasswords")),
    )


def downgrade():
    op.drop_table("UserPasswords")
