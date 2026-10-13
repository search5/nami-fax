"""create DynConf

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-01

Only creates the table when the legacy SQLite schema code has not already done so.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("DynConf"):
        return
    op.create_table(
        "DynConf",
        sa.Column("dynconf_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device", sa.String(length=64), nullable=True),
        sa.Column("callid", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("dynconf_id", name=op.f("pk_DynConf")),
    )


def downgrade():
    op.drop_table("DynConf")
