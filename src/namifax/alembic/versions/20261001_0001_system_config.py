"""create SystemConfig

Revision ID: 0001
Revises:
Create Date: 2026-10-01

Baseline for the ORM-managed tables. SQLite databases created by earlier versions of the port may already
have this table, so the upgrade only creates it when it is missing. Other databases get it from this migration.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("SystemConfig"):
        return
    op.create_table(
        "SystemConfig",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_SystemConfig")),
    )


def downgrade():
    op.drop_table("SystemConfig")
