"""rename SysLog.log_id to syslogid, the name of the legacy AvantFAX schema

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def _columns():
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("SysLog")}


def upgrade():
    if "log_id" not in _columns():          # a database that already has the legacy name
        return
    # batch mode: a plain RENAME COLUMN on SQLite 3.25+, an ALTER (keeping AUTO_INCREMENT) elsewhere
    with op.batch_alter_table("SysLog") as batch:
        batch.alter_column("log_id", new_column_name="syslogid", existing_type=sa.Integer(),
                           existing_nullable=False, existing_autoincrement=True)


def downgrade():
    if "syslogid" not in _columns():
        return
    with op.batch_alter_table("SysLog") as batch:
        batch.alter_column("syslogid", new_column_name="log_id", existing_type=sa.Integer(),
                           existing_nullable=False, existing_autoincrement=True)
