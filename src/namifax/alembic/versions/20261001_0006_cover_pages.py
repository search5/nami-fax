"""create CoverPages

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-01

Only creates the table when the legacy SQLite schema code has not already done so.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("CoverPages"):
        return
    op.create_table(
        "CoverPages",
        sa.Column("cover_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("file", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("cover_id", name=op.f("pk_CoverPages")),
    )


def downgrade():
    op.drop_table("CoverPages")
