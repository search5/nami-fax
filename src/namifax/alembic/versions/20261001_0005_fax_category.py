"""create FaxCategory

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-01

Only creates the table when the legacy SQLite schema code has not already done so.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("FaxCategory"):
        return
    op.create_table(
        "FaxCategory",
        sa.Column("catid", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("catid", name=op.f("pk_FaxCategory")),
        sa.UniqueConstraint("name", name=op.f("uq_FaxCategory_name")),
    )


def downgrade():
    op.drop_table("FaxCategory")
