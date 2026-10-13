"""create SysLog

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-01

Only creates the table when the legacy SQLite schema code has not already done so.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("SysLog"):
        return
    op.create_table(
        "SysLog",
        sa.Column("log_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("logdate", sa.String(length=32), nullable=False),
        sa.Column("logtext", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("log_id", name=op.f("pk_SysLog")),
    )


def downgrade():
    op.drop_table("SysLog")
