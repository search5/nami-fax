"""widen SystemSettings.smtp_password for the encrypted value

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    # batch mode rebuilds the table on SQLite (which cannot alter a column in place) and is a plain ALTER elsewhere
    with op.batch_alter_table("SystemSettings") as batch:
        batch.alter_column("smtp_password", existing_type=sa.String(length=255), type_=sa.String(length=512),
                           existing_nullable=True)


def downgrade():
    with op.batch_alter_table("SystemSettings") as batch:
        batch.alter_column("smtp_password", existing_type=sa.String(length=512), type_=sa.String(length=255),
                           existing_nullable=True)
