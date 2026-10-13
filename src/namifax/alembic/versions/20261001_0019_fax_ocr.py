"""create FaxOCR

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("FaxOCR"):
        return
    op.create_table(
        "FaxOCR",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fax_id", sa.Integer(), nullable=True),
        sa.Column("fax_file", sa.String(length=255), nullable=False),
        sa.Column("ocr_text", sa.Text().with_variant(mysql.LONGTEXT(), "mysql", "mariadb"), nullable=False),
        sa.Column("page_count", sa.Integer(), server_default="1", nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_FaxOCR")),
    )
    op.create_index(op.f("ix_FaxOCR_fax_id"), "FaxOCR", ["fax_id"], unique=False)
    op.create_index(op.f("ix_FaxOCR_fax_file"), "FaxOCR", ["fax_file"], unique=False)


def downgrade():
    op.drop_table("FaxOCR")
