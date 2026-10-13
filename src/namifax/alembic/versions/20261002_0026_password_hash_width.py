"""password columns wide enough for an Argon2id hash (the original's columns hold a 32-character MD5)

Rows keep their MD5 value until the owner's next login, so the original program keeps working for accounts that have not logged in
to this one (set NAMIFAX_PASSWORD_HASH=md5 to keep it working for everybody).

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("UserAccount") as batch:
        batch.alter_column("password", existing_type=sa.String(64), type_=sa.String(255), existing_nullable=False)
    with op.batch_alter_table("UserPasswords") as batch:
        batch.alter_column("pwdhash", existing_type=sa.String(64), type_=sa.String(255), existing_nullable=False)


def downgrade():
    # hashes longer than the old width cannot be kept: such accounts need a new password after a downgrade
    with op.batch_alter_table("UserAccount") as batch:
        batch.alter_column("password", existing_type=sa.String(255), type_=sa.String(64), existing_nullable=False)
    with op.batch_alter_table("UserPasswords") as batch:
        batch.alter_column("pwdhash", existing_type=sa.String(255), type_=sa.String(64), existing_nullable=False)
