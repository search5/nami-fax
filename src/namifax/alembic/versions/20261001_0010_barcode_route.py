"""create BarcodeRoute

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-01

Only creates the table when the legacy SQLite schema code has not already done so.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("BarcodeRoute"):
        return
    op.create_table(
        "BarcodeRoute",
        sa.Column("barcode_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("barcode", sa.String(length=255), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=True),
        sa.Column("contact", sa.String(length=255), nullable=True),
        sa.Column("printer", sa.String(length=255), nullable=True),
        sa.Column("faxcatid", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("barcode_id", name=op.f("pk_BarcodeRoute")),
        sa.UniqueConstraint("barcode", name=op.f("uq_BarcodeRoute_barcode")),
    )


def downgrade():
    op.drop_table("BarcodeRoute")
