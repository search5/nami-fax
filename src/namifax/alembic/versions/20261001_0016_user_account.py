"""create UserAccount

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-01

Only creates the table when the legacy SQLite schema code has not already done so.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("UserAccount"):
        return
    op.create_table(
        "UserAccount",
        sa.Column("uid", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("email_sig", sa.Text(), nullable=True),
        sa.Column("user_tsi", sa.String(length=255), nullable=True),
        sa.Column("from_company", sa.String(length=255), nullable=True),
        sa.Column("from_location", sa.String(length=255), nullable=True),
        sa.Column("from_voicenumber", sa.String(length=255), nullable=True),
        sa.Column("from_faxnumber", sa.String(length=255), nullable=True),
        sa.Column("coverpage_id", sa.Integer(), nullable=True),
        sa.Column("audiofile", sa.String(length=255), nullable=True),
        sa.Column("faxperpageinbox", sa.Integer(), server_default="10", nullable=True),
        sa.Column("faxperpagearchive", sa.Integer(), server_default="10", nullable=True),
        sa.Column("superuser", sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.Column("can_del", sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.Column("last_mod", sa.String(length=32), nullable=True),
        sa.Column("last_login", sa.String(length=32), nullable=True),
        sa.Column("last_ip", sa.String(length=45), nullable=True),
        sa.Column("language", sa.String(length=16), server_default="en", nullable=True),
        sa.Column("modemdevs", sa.Text(), nullable=True),
        sa.Column("didrouting", sa.Text(), nullable=True),
        sa.Column("faxcats", sa.Text(), nullable=True),
        sa.Column("pwdexpire", sa.String(length=32), nullable=True),
        sa.Column("pwdcycle", sa.Integer(), server_default="0", nullable=True),
        sa.Column("pwd_reuse", sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.Column("wasreset", sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.Column("acc_enabled", sa.Boolean(), server_default=sa.true(), nullable=True),
        sa.Column("deleted", sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.Column("any_modem", sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.PrimaryKeyConstraint("uid", name=op.f("pk_UserAccount")),
        sa.UniqueConstraint("username", name=op.f("uq_UserAccount_username")),
    )
    op.create_index(op.f("ix_UserAccount_email"), "UserAccount", ["email"], unique=False)


def downgrade():
    op.drop_table("UserAccount")
