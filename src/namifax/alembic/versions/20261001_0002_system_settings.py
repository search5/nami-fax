"""create SystemSettings

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01

Only creates the table when the legacy SQLite schema code has not already done so.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("SystemSettings"):
        return
    op.create_table(
        "SystemSettings",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("smtp_host", sa.String(length=255), server_default="localhost", nullable=True),
        sa.Column("smtp_port", sa.Integer(), server_default="25", nullable=True),
        sa.Column("smtp_security", sa.String(length=16), server_default="NONE", nullable=True),
        sa.Column("smtp_auth", sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.Column("smtp_username", sa.String(length=255), nullable=True),
        sa.Column("smtp_password", sa.String(length=255), nullable=True),
        sa.Column("from_email", sa.String(length=255), server_default="root@localhost", nullable=True),
        sa.Column("from_name", sa.String(length=255), server_default="NamiFAX", nullable=True),
        sa.Column("email_sig_text", sa.Text(), nullable=True),
        sa.Column("email_sig_html", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_SystemSettings")),
    )


def downgrade():
    op.drop_table("SystemSettings")
