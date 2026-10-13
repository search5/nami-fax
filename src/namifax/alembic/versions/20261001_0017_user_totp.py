"""create UserTOTP

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("UserTOTP"):
        return
    op.create_table(
        "UserTOTP",
        sa.Column("uid", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("secret_key", sa.String(length=255), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.Column("backup_codes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint("uid", name=op.f("pk_UserTOTP")),
    )


def downgrade():
    op.drop_table("UserTOTP")
