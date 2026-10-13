"""B0-4: starter-style fixtures (tm, dbsession, app_request, testapp, dummy_request) roll back after each test."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def test_dbsession_is_joined_to_the_doomed_transaction(dbsession, tm):
    assert isinstance(dbsession, Session)
    assert tm.get().isDoomed()


def test_writes_are_discarded_when_the_transaction_is_aborted(dbsession, tm):
    import zope.sqlalchemy

    dbsession.execute(text("INSERT INTO SystemConfig (key, value) VALUES ('t1', 'v')"))
    zope.sqlalchemy.mark_changed(dbsession)
    assert dbsession.execute(text("SELECT COUNT(*) FROM SystemConfig WHERE key = 't1'")).scalar() == 1

    tm.abort()
    tm.begin()
    assert dbsession.execute(text("SELECT COUNT(*) FROM SystemConfig WHERE key = 't1'")).scalar() == 0


def test_app_request_shares_the_fixture_session_and_manager(app_request, dbsession, tm):
    assert app_request.dbsession is dbsession
    assert app_request.tm is tm


def test_dummy_request_carries_session_and_manager(dummy_request, dbsession, tm):
    assert dummy_request.dbsession is dbsession
    assert dummy_request.tm is tm


def test_testapp_serves_requests_with_the_shared_session(testapp):
    res = testapp.get("/login", status=200)
    assert "login" in res.text.lower()


def test_each_test_gets_its_own_database(app, dbengine):
    with dbengine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM SystemConfig WHERE key = 't1'")).scalar()
    assert n == 0  # written (and rolled back) by another test
