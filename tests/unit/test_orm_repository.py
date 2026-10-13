"""ORM-backed Repository: the MDBOData API on a SQLAlchemy session (portable across databases)."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def repo(dbsession):
    from namifax.db.repository import Repository

    dbsession.execute(sa.text("DELETE FROM FaxCategory"))
    return Repository("FaxCategory", db=dbsession)


# --- dispatch ----------------------------------------------------------------------------

def test_repository_with_a_session_is_orm_backed(dbsession):
    from namifax.db.orm_repository import OrmRepository
    from namifax.db.repository import MDBOData, Repository

    assert isinstance(Repository("FaxCategory", db=dbsession), OrmRepository)
    assert isinstance(MDBOData("FaxCategory", db=dbsession), OrmRepository)


def test_unknown_table_without_an_orm_model_is_reported(dbsession):
    from namifax.db.repository import Repository

    with pytest.raises(LookupError, match="no ORM model"):
        Repository("NoSuchTable", db=dbsession)


# --- create / read -----------------------------------------------------------------------

def test_new_entry_inserts_and_exposes_the_new_id(repo):
    assert repo.new_entry({"name": "Invoices"}) is True
    assert repo.get_id() > 0
    assert repo.find({"name": "Invoices"}) == {"catid": repo.get_id(), "name": "Invoices"}


def test_find_without_conditions_lists_everything_in_primary_key_order(repo):
    for name in ("b", "a", "c"):
        repo.new_entry({"name": name})
    rows = repo.find(reduce_single=False)
    assert [r["name"] for r in rows] == ["b", "a", "c"]
    assert [r["catid"] for r in rows] == sorted(r["catid"] for r in rows)


def test_find_reduces_a_single_match_to_a_dict_but_not_a_list(repo):
    repo.new_entry({"name": "only"})
    assert isinstance(repo.find({"name": "only"}), dict)
    assert isinstance(repo.find({"name": "only"}, reduce_single=False), list)
    assert repo.find({"name": "nobody"}) == []


def test_find_with_or_logic_limit_and_offset(repo):
    for name in ("a", "b", "c", "d"):
        repo.new_entry({"name": name})
    from namifax.db.orm_repository import SQL_OR

    assert {r["name"] for r in repo.find({"name": "a", "catid": 999}, query_logic=SQL_OR, reduce_single=False)} == {"a"}
    page = repo.find(limit=2, offset=1, reduce_single=False)
    assert [r["name"] for r in page] == ["b", "c"]


def test_numeric_strings_match_integer_columns(repo):
    repo.new_entry({"name": "x"})
    pk = repo.get_id()
    assert repo.find({"catid": str(pk)})["name"] == "x"  # PHP-style loose typing, also on PostgreSQL
    assert repo.find({"catid": "not a number"}, reduce_single=False) == []


def test_comparing_with_none_matches_nothing_like_sql_equals_null(repo):
    repo.new_entry({"name": "x"})
    assert repo.find({"name": None}, reduce_single=False) == []


def test_unknown_keys_are_ignored(repo):
    assert repo.new_entry({"name": "known", "bogus": 1}) is True
    assert repo.find({"name": "known"})["name"] == "known"


def test_values_with_quotes_backslashes_and_unicode_round_trip(repo):
    tricky = "o'brien\\' OR 1=1 -- \"q\" 한글"
    repo.new_entry({"name": tricky})
    assert repo.find({"name": tricky})["name"] == tricky


# --- load / update / delete --------------------------------------------------------------

def test_load_fills_the_record(repo):
    repo.new_entry({"name": "loadme"})
    pk = repo.get_id()
    other = type(repo)(repo.model, repo.session)
    assert other.load(pk) is True
    assert other.get_id() == pk and other.get_info()["name"] == "loadme"
    assert other.load(99999) is False


def test_update_entry_changes_the_selected_row_only(repo):
    repo.new_entry({"name": "keep"})
    repo.new_entry({"name": "old"})
    pk = repo.get_id()
    repo.data.set_id(pk)
    assert repo.update_entry({"name": "new"}) is True
    assert [r["name"] for r in repo.find(reduce_single=False)] == ["keep", "new"]


def test_a_primary_key_in_the_payload_selects_the_row_and_is_never_rewritten(repo):
    """Legacy: the payload is applied to the record first, so services can pass a whole loaded row."""
    repo.new_entry({"name": "x"})
    pk = repo.get_id()
    other = type(repo)(repo.model, repo.session)
    assert other.update_entry({"catid": pk, "name": "y"}) is True
    assert repo.find({"name": "y"})["catid"] == pk
    assert repo.find({"name": "x"}) == []


def test_update_or_delete_of_a_missing_row_succeeds_like_the_legacy_sql(repo):
    repo.data.set_id(424242)
    assert repo.update_entry({"name": "ghost"}) is True
    assert repo.delete_entry() is True
    assert repo.find(reduce_single=False) == []


def test_delete_entry_removes_the_row_and_needs_an_id(repo):
    repo.new_entry({"name": "gone"})
    pk = repo.get_id()
    repo.data.set_id(pk)
    assert repo.delete_entry() is True
    assert repo.find({"catid": pk}, reduce_single=False) == []
    fresh = type(repo)(repo.model, repo.session)
    assert fresh.delete_entry() is False  # no id selected


def test_set_id_validates_like_the_legacy_entity(repo):
    assert repo.data.set_id("7") is True and repo.data.get_id() == 7
    assert repo.data.set_id("x") is False


# --- ordered listing (replaces the raw SELECT ... ORDER BY strings) -------------------------

def test_select_returns_ordered_rows_and_selected_columns(repo):
    for name in ("b", "c", "a"):
        repo.new_entry({"name": name})
    assert [r["name"] for r in repo.select(order_by="name")] == ["a", "b", "c"]
    assert [r["name"] for r in repo.select(order_by="name", descending=True)] == ["c", "b", "a"]
    assert repo.select(columns=["name"], order_by="name")[0] == {"name": "a"}


def test_raw_sql_is_not_supported_on_the_orm_repository(repo):
    with pytest.raises(NotImplementedError, match="select"):
        repo.query("SELECT * FROM FaxCategory")


def test_unique_violations_surface_as_exceptions(repo):
    repo.new_entry({"name": "dup"})
    with pytest.raises(IntegrityError):
        repo.new_entry({"name": "dup"})


# --- real servers (optional) -------------------------------------------------------------

@pytest.mark.serverdb
def test_server_database_repository_behaviour(monkeypatch, server_db_url, alembic_cfg):
    import alembic.command
    from sqlalchemy.orm import Session

    from namifax.db.orm_repository import SQL_OR
    from namifax.db.repository import Repository

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as session:
            repo = Repository("FaxCategory", db=session)
            for name in ("b", "a", "한글 'q' \\x", "d"):
                assert repo.new_entry({"name": name}) is True
            pk = repo.get_id()
            assert repo.find({"catid": str(pk)})["name"] == "d"            # "5" vs INTEGER: PostgreSQL needs the cast
            assert repo.find({"catid": "abc"}, reduce_single=False) == []
            assert repo.find({"name": None}, reduce_single=False) == []     # = NULL matches nothing
            assert repo.find({"name": "한글 'q' \\x"})["name"] == "한글 'q' \\x"
            assert {r["name"] for r in repo.find({"name": "a", "catid": 99999}, query_logic=SQL_OR,
                                                  reduce_single=False)} == {"a"}
            assert [r["name"] for r in repo.find(limit=2, offset=1, reduce_single=False)] == ["a", "한글 'q' \\x"]
            ordered = [r["name"] for r in repo.select(order_by="name")]
            assert set(ordered) == {"b", "a", "한글 'q' \\x", "d"}
            assert [n for n in ordered if n.isascii()] == ["a", "b", "d"]  # collation decides where 한글 goes
            with pytest.raises(IntegrityError):
                repo.new_entry({"name": "a"})
            session.rollback()

            repo = Repository("FaxCategory", db=session)
            repo.new_entry({"name": "to-rename"})
            repo.update_entry({"catid": repo.get_id(), "name": "renamed"})
            assert repo.find({"name": "renamed"})["catid"] == repo.get_id()
            repo.data.set_id(repo.get_id())
            assert repo.delete_entry() is True and repo.find({"name": "renamed"}, reduce_single=False) == []

            for name in ("Acme Corp", "100% Fax", "100 Fax", "file_name", "fileXname", "한글 'q' \\x"):   # rollback above dropped the earlier rows
                repo.new_entry({"name": name})
            found = lambda text: [r["name"] for r in repo.search_text("name", text, order_by="name")]  # noqa: E731
            assert found("ACME") == ["Acme Corp"] and found("acm corp") == ["Acme Corp"] and found("corp acm") == []
            assert found("100%") == ["100% Fax"] and found("file_name") == ["file_name"]
            assert found("x'/**/OR/**/1=1--") == [] and found("한글") == ["한글 'q' \\x"]
            session.commit()
    finally:
        engine.dispose()


# --- search_text: the same safe, portable search on both repository implementations ---------------

def test_search_text_is_case_insensitive_ordered_and_literal_on_both_backends(dbsession, seeded_db):
    from namifax.db.repository import Repository

    for backend in (dbsession, seeded_db):
        if backend is dbsession:
            backend.execute(sa.text("DELETE FROM FaxCategory"))
        else:
            backend.query("DELETE FROM FaxCategory")
        repo = Repository("FaxCategory", db=backend)
        for name in ("Acme Corp", "100% Fax", "100 Fax", "file_name", "fileXname", "O'Brien \\ & Co"):
            repo.new_entry({"name": name})
        names = lambda text: [r["name"] for r in repo.search_text("name", text, order_by="name")]  # noqa: E731
        assert names("ACME") == ["Acme Corp"]
        assert names("acm corp") == ["Acme Corp"] and names("corp acm") == []
        assert names("100%") == ["100% Fax"] and names("file_name") == ["file_name"]
        assert names("o'brien") == ["O'Brien \\ & Co"]
        assert names("' OR 1=1 --") == [] and names("x\\' OR 1=1") == []


