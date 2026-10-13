"""create Modems

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-01

Only creates the table when the legacy SQLite schema code has not already done so.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("Modems"):
        return
    op.create_table(
        "Modems",
        sa.Column("devid", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device", sa.String(length=64), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=True),
        sa.Column("contact", sa.String(length=255), nullable=True),
        sa.Column("printer", sa.String(length=255), nullable=True),
        sa.Column("faxcatid", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("devid", name=op.f("pk_Modems")),
        sa.UniqueConstraint("device", name=op.f("uq_Modems_device")),
    )


def downgrade():
    op.drop_table("Modems")
