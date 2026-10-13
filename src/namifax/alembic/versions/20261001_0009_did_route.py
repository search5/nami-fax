"""create DIDRoute

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-01

Only creates the table when the legacy SQLite schema code has not already done so.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("DIDRoute"):
        return
    op.create_table(
        "DIDRoute",
        sa.Column("didr_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("routecode", sa.String(length=64), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=True),
        sa.Column("contact", sa.String(length=255), nullable=True),
        sa.Column("printer", sa.String(length=255), nullable=True),
        sa.Column("faxcatid", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("didr_id", name=op.f("pk_DIDRoute")),
        sa.UniqueConstraint("routecode", name=op.f("uq_DIDRoute_routecode")),
    )


def downgrade():
    op.drop_table("DIDRoute")
