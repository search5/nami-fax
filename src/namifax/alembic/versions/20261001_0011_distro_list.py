"""create DistroList

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-01

Only creates the table when the legacy SQLite schema code has not already done so.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("DistroList"):
        return
    op.create_table(
        "DistroList",
        sa.Column("dl_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("listname", sa.String(length=255), nullable=False),
        sa.Column("listdata", sa.Text(), nullable=True),
        sa.Column("lastmod_date", sa.String(length=32), nullable=True),
        sa.Column("lastmod_user", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("dl_id", name=op.f("pk_DistroList")),
    )


def downgrade():
    op.drop_table("DistroList")
