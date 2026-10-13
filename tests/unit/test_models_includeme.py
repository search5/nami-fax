"""B0-2: models.includeme wires pyramid_tm, pyramid_retry and the dbsession request method like the Pyramid starter."""

from __future__ import annotations

import sqlite3

import pytest
import zope.sqlalchemy
from pyramid.interfaces import IExecutionPolicy
from pyramid.scripting import prepare
from sqlalchemy import text
from sqlalchemy.orm import Session


@pytest.fixture
def app_and_file(tmp_path):
    from namifax import create_app

    db_file = tmp_path / "orm.db"
    return create_app(**{"sqlalchemy.url": f"sqlite:///{db_file}"}), db_file


def test_get_tm_session_is_exported():
    from namifax import models

    assert callable(models.get_tm_session)


def test_tm_manager_hook_is_configured_before_pyramid_tm_is_included(app_and_file):
    import pyramid_tm

    app, _ = app_and_file
    assert app.registry.settings["tm.manager_hook"] in ("pyramid_tm.explicit_manager", pyramid_tm.explicit_manager)
    with prepare(registry=app.registry) as env:
        assert env["request"].tm.explicit is True


def test_pyramid_retry_execution_policy_is_active(app_and_file):
    from pyramid.router import default_execution_policy

    app, _ = app_and_file
    policy = app.registry.queryUtility(IExecutionPolicy)
    assert policy is not None and policy is not default_execution_policy


def test_dbsession_is_a_session_joined_to_the_request_transaction(app_and_file):
    app, db_file = app_and_file
    with prepare(registry=app.registry) as env:
        request = env["request"]
        request.tm.begin()  # the pyramid_tm tween does this before the view runs
        assert isinstance(request.dbsession, Session)
        assert request.dbsession is request.dbsession
        request.dbsession.execute(text("INSERT INTO SystemConfig (key, value) VALUES ('k1', 'v1')"))
        # zope.sqlalchemy only commits sessions it knows are changed; ORM flushes mark them
        # automatically, raw SQL does not.
        zope.sqlalchemy.mark_changed(request.dbsession)
        request.tm.commit()

    con = sqlite3.connect(db_file)
    try:
        assert con.execute("SELECT value FROM SystemConfig WHERE key = 'k1'").fetchone() == ("v1",)
    finally:
        con.close()


def test_aborted_request_transaction_discards_session_writes(app_and_file):
    app, db_file = app_and_file
    with prepare(registry=app.registry) as env:
        request = env["request"]
        request.tm.begin()
        request.dbsession.execute(text("INSERT INTO SystemConfig (key, value) VALUES ('k2', 'v2')"))
        request.tm.abort()

    con = sqlite3.connect(db_file)
    try:
        assert con.execute("SELECT value FROM SystemConfig WHERE key = 'k2'").fetchone() is None
    finally:
        con.close()


def test_environ_hook_lets_tests_share_a_session(app_and_file):
    app, _ = app_and_file
    shared = object()
    with prepare(registry=app.registry) as env:
        request = env["request"]
        request.environ["app.dbsession"] = shared
        assert request.dbsession is shared


def test_dbengine_setting_hook_is_honoured(tmp_path):
    from namifax import create_app
    from namifax.db.provider import create_sa_engine

    engine = create_sa_engine(f"sqlite:///{tmp_path / 'hook.db'}")
    app = create_app(dbengine=engine)
    assert app.registry["dbengine"] is engine


def test_raw_sql_without_mark_changed_is_rolled_back(app_and_file):
    """Documents the zope.sqlalchemy contract the request.db bridge has to honour."""
    app, db_file = app_and_file
    with prepare(registry=app.registry) as env:
        request = env["request"]
        request.tm.begin()
        request.dbsession.execute(text("INSERT INTO SystemConfig (key, value) VALUES ('k3', 'v3')"))
        request.tm.commit()

    con = sqlite3.connect(db_file)
    try:
        assert con.execute("SELECT value FROM SystemConfig WHERE key = 'k3'").fetchone() is None
    finally:
        con.close()
