"""create UserWebAuthnCredentials

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("UserWebAuthnCredentials"):
        return
    op.create_table(
        "UserWebAuthnCredentials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uid", sa.Integer(), nullable=False),
        sa.Column("credential_id", sa.String(length=255), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("sign_count", sa.Integer(), server_default="0", nullable=True),
        sa.Column("transports", sa.String(length=100), nullable=True),
        sa.Column("device_name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=True),
        sa.Column("last_used_at", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_UserWebAuthnCredentials")),
        sa.UniqueConstraint("credential_id", name=op.f("uq_UserWebAuthnCredentials_credential_id")),
    )
    op.create_index(op.f("ix_UserWebAuthnCredentials_uid"), "UserWebAuthnCredentials", ["uid"], unique=False)


def downgrade():
    op.drop_table("UserWebAuthnCredentials")
