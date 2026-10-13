Migration scripts live here.

    alembic -c development.ini revision --autogenerate -m "describe the change"
    alembic -c development.ini upgrade head

The target database is resolved like the application does: ``sqlalchemy.url`` in the ini file,
then DATABASE_URL, AFDB_URL and NAMIFAX_DB_PATH.
