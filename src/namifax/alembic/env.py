"""Pyramid bootstrap environment for Alembic.

The database URL is resolved exactly like the application does (``sqlalchemy.url`` in the ini
file, then ``DATABASE_URL`` / ``AFDB_URL`` / ``NAMIFAX_DB_PATH``), so migrations and the running
app always target the same database.
"""

import os

from alembic import context
from pyramid.paster import get_appsettings, setup_logging

from namifax.db.provider import create_sa_engine, resolve_database_url
from namifax.models.meta import Base

# Import the models package so every table is attached to ``Base.metadata``.
import namifax.models  # noqa: F401

config = context.config

# An ini file is present when alembic is run from the command line. The application itself upgrades
# the schema at start-up and hands over its open connection instead (see namifax.db.bootstrap).
if config.config_file_name:
    setup_logging(config.config_file_name)
    settings = get_appsettings(config.config_file_name)
else:
    settings = {}
database_url = resolve_database_url(settings, os.environ) if config.config_file_name else None
target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though an Engine is
    acceptable here as well. By skipping the Engine creation we don't even need a DBAPI to be
    available. Calls to context.execute() here emit the given string to the script output.
    """
    context.configure(url=database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode with an Engine and a connection."""
    existing = config.attributes.get("connection")
    if existing is not None:
        context.configure(connection=existing, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_sa_engine(database_url)

    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
