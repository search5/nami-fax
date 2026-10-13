"""create FaxArchive

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("FaxArchive"):
        return
    op.create_table(
        "FaxArchive",
        sa.Column("fid", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("faxnumid", sa.Integer(), nullable=True),
        sa.Column("companyid", sa.Integer(), nullable=True),
        sa.Column("faxpath", sa.String(length=255), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=True),
        sa.Column("faxcatid", sa.Integer(), nullable=True),
        sa.Column("didr_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("lastoperation", sa.String(length=32), nullable=True),
        sa.Column("lastmoduser", sa.Integer(), nullable=True),
        sa.Column("lastmoddate", sa.String(length=32), nullable=True),
        sa.Column("archstamp", sa.String(length=32), nullable=True),
        sa.Column("modemdev", sa.String(length=64), nullable=True),
        sa.Column("userid", sa.Integer(), nullable=True),
        sa.Column("origfaxnum", sa.String(length=32), nullable=True),
        sa.Column("faxcontent", sa.Text(), nullable=True),
        sa.Column("inbox", sa.Integer(), server_default="1", nullable=True),
        sa.PrimaryKeyConstraint("fid", name=op.f("pk_FaxArchive")),
    )
    for col in ("faxnumid", "companyid", "archstamp", "userid", "inbox"):
        op.create_index(op.f(f"ix_FaxArchive_{col}"), "FaxArchive", [col], unique=False)


def downgrade():
    op.drop_table("FaxArchive")
