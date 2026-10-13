"""add the failed-attempt counter and lock time to UserTOTP

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def _columns():
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("UserTOTP")}


def upgrade():
    existing = _columns()
    if "failed_attempts" not in existing:
        op.add_column("UserTOTP", sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=True))
    if "locked_until" not in existing:
        op.add_column("UserTOTP", sa.Column("locked_until", sa.String(length=32), nullable=True))


def downgrade():
    op.drop_column("UserTOTP", "locked_until")
    op.drop_column("UserTOTP", "failed_attempts")
