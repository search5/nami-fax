"""B track, group 4: FaxArchive searched through the ORM.

The answers to a matrix of search criteria were recorded from the original SQL implementation before it was
removed (``data/fax_archive_search_golden.json``); the ORM queries must keep giving exactly those answers. The
same matrix runs on the real servers in the serverdb test.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable


LEGACY_COLUMNS = {"fid", "faxnumid", "companyid", "faxpath", "pages", "faxcatid", "didr_id", "description",
                  "lastoperation", "lastmoduser", "lastmoddate", "archstamp", "modemdev", "userid", "origfaxnum",
                  "faxcontent", "inbox"}


def test_model_maps_the_legacy_table():
    from namifax.models import FaxArchive

    t = FaxArchive.__table__
    assert t.name == "FaxArchive" and [c.name for c in t.primary_key.columns] == ["fid"]
    assert set(t.c.keys()) == LEGACY_COLUMNS
    assert not t.c.faxpath.nullable and t.c.faxpath.type.length == 255
    for d in (sqlite.dialect(), mysql.dialect(), postgresql.dialect()):
        assert "PRIMARY KEY (fid)" in str(CreateTable(t).compile(dialect=d))


# --- the data set --------------------------------------------------------------------------------------

def _row(fid, **kw):
    base = dict(fid=fid, faxpath=f"/fax/{fid}", pages=1, inbox=0, faxnumid=None, companyid=None, faxcatid=None,
                didr_id=None, modemdev=None, userid=None, archstamp="2026-01-01 00:00:00", description=None,
                faxcontent=None, origfaxnum="555")
    base.update(kw)
    return base


ROWS = [
    _row(1, inbox=1, modemdev="ttyS0", didr_id=1),
    _row(2, inbox=1, modemdev="ttyS0", faxcatid=1, didr_id=1),
    _row(3, inbox=1, modemdev="ttyS1", faxcatid=2, didr_id=2),
    _row(4, inbox=1, modemdev="ttyS1"),
    _row(5, modemdev="ttyS0", faxnumid=1, archstamp="2026-01-05 10:00:00", description="Invoice March",
         faxcontent="total due"),
    _row(6, modemdev="ttyS1", userid=0, faxcatid=1, faxnumid=2, archstamp="2026-01-20 09:00:00",
         description="Contract draft", faxcontent="Signed by ACME"),
    _row(7, modemdev="ttyS0", faxcatid=2, companyid=7, archstamp="2026-02-03 12:00:00"),
    _row(8, userid=5, archstamp="2026-02-10 08:00:00", description="Sent invoice"),
    _row(9, userid=6, archstamp="2026-02-11 08:00:00"),
    _row(10, modemdev="ttyS2", didr_id=2, faxcatid=1, archstamp="2026-03-01 07:00:00", description="Receipt"),
    _row(11, userid=5, faxcatid=2, archstamp="2026-03-02 07:00:00"),
    _row(12, modemdev="ttyS0", didr_id=1, faxnumid=3, archstamp="2026-03-15 07:00:00", description="invoice april"),
]
FAX_NUMBERS = [(1, 10), (2, 11), (3, 10)]          # abookfax_id, abook_id


def _load_session(session):
    from namifax.models import AddressBookFAX, FaxArchive

    session.execute(sa.delete(FaxArchive))
    session.execute(sa.delete(AddressBookFAX))
    session.add_all([FaxArchive(**r) for r in ROWS])
    session.add_all([AddressBookFAX(abookfax_id=i, abook_id=a, faxnumber=f"5{i}") for i, a in FAX_NUMBERS])
    session.flush()
    from conftest import sync_sequences

    sync_sequences(session.connection())                        # the rows above carry their own ids


@pytest.fixture
def orm(dbsession):
    _load_session(dbsession)
    return dbsession


@pytest.fixture
def backend(orm):
    return orm


def _archive(db):
    from namifax.services.archive_base import FaxPDFArchive

    return FaxPDFArchive(db=db)


GOLDEN = json.loads((Path(__file__).parent / "data" / "fax_archive_search_golden.json").read_text())


def _search(db, **criteria):
    arc = _archive(db)
    n = arc.search_archive(criteria)
    fids = []
    while (fid := arc.next_archive_entry()) is not None:
        fids.append(fid)
    return n, fids


# --- the search matrix (identical answers from both paths) ---------------------------------------------------

BASE = {"pagelimit": 50}
CASES = []
for sr, sup in itertools.product(["s", "r", "*", "b"], [True, False]):
    CASES.append(dict(sentrecvd=sr, superuser=sup, userid=5, modemdevs=["ttyS0"], categories=[1], didroutes=[1]))
    CASES.append(dict(sentrecvd=sr, superuser=sup, userid=5, modemdevs=["ttyS0", "ttyS1"], categories=None, didroutes=None))
    # (no routes at all for a non-superuser in the "other" search made the legacy SQL invalid: tested separately)
    CASES.append(dict(sentrecvd=sr, superuser=sup, userid=6, modemdevs=["ttyS2"], categories=[2], didroutes=[2]))
    CASES.append(dict(sentrecvd=sr, superuser=sup, userid=5, modemdevs=["ttyS0"], categories=[1, 2], restricted_user_mode=True))
    CASES.append(dict(sentrecvd=sr, superuser=sup, userid=5, modemdevs=["ttyS0"], enable_did_routing=True, didroutes=[1, 2], categories=[2]))
    CASES.append(dict(sentrecvd=sr, superuser=sup, userid=5, modemdevs=["ttyS1"], category=1))
CASES += [
    dict(sentrecvd="r", superuser=True, start_date="2026-01-01", end_date="2026-02-05"),
    dict(sentrecvd="r", superuser=True, start_date="2026-03"),
    dict(sentrecvd="r", superuser=True, keywords="invoice"),
    dict(sentrecvd="*", superuser=True, keywords="INVOICE"),
    dict(sentrecvd="*", superuser=True, keywords="signed acme"),
    dict(sentrecvd="*", superuser=True, keywords="due"),
    dict(sentrecvd="*", superuser=True, faxid=7),
    dict(sentrecvd="*", superuser=True, companyid=10),
    dict(sentrecvd="*", superuser=True, companyid=7),
    dict(sentrecvd="*", superuser=True, companyid=11),
    dict(sentrecvd="*", superuser=True, companyid=99),
    dict(sentrecvd="*", superuser=True, keywords="invoice", companyid=10),
    dict(sentrecvd="s", superuser=True, userid=5, start_date="2026-03"),
    dict(sentrecvd="r", superuser=False, modemdevs=[""], categories=None),
    dict(sentrecvd="r", superuser=False, enable_did_routing=True, didroutes=[""], categories=None),
]


def _ids(c):
    return ",".join(f"{k}={v}" for k, v in c.items())


def test_the_recorded_matrix_is_the_one_in_this_file():
    assert [g["case"] for g in GOLDEN["search"]] == CASES


@pytest.mark.parametrize("golden", GOLDEN["search"], ids=[_ids(g["case"]) for g in GOLDEN["search"]])
def test_search_gives_the_recorded_answer(golden, orm):
    assert _search(orm, **BASE, **golden["case"]) == (golden["numrows"], golden["fids"])


def test_search_sanity_so_the_matrix_is_not_vacuous(orm):
    assert _search(orm, **BASE, sentrecvd="*", superuser=True)[0] == 8                  # every archived fax
    assert _search(orm, **BASE, sentrecvd="s", superuser=True)[1] == [11, 9, 8]
    assert _search(orm, **BASE, sentrecvd="*", superuser=True, companyid=10)[1] == [12, 5]


@pytest.mark.parametrize("pageindex,expected", [(0, [12, 11, 10]), (1, [9, 8, 7]), (2, [6, 5]), (9, [6, 5]), (-3, [12, 11, 10])])
def test_paging(pageindex, expected, orm):
    kw = dict(sentrecvd="*", superuser=True, pagelimit=3, pageindex=pageindex)
    assert _search(orm, **kw) == (8, expected)


@pytest.mark.parametrize("golden", GOLDEN["paging"], ids=["page-1", "page-out-of-range"])
def test_recorded_paging_answers(golden, orm):
    assert _search(orm, **golden["case"]) == (golden["numrows"], golden["fids"])


def test_user_search_without_a_user_or_routes_does_not_crash(orm):
    """The legacy code built invalid SQL here (``userid = None``); the ORM path just matches nothing extra."""
    n, fids = _search(orm, **BASE, sentrecvd="*", superuser=False, modemdevs=["ttyS0"], userid=None)
    assert fids == [12, 7, 5]
    n, fids = _search(orm, **BASE, sentrecvd="x", superuser=False, userid=5, modemdevs=None)
    assert fids == [11, 8]


def test_keyword_wildcards_are_literal(orm):
    assert _search(orm, **BASE, sentrecvd="*", superuser=True, keywords="%")[1] == []
    assert _search(orm, **BASE, sentrecvd="*", superuser=True, keywords="x' OR '1'='1")[1] == []


# --- the inbox ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("golden", GOLDEN["inbox"], ids=[str(g["args"]) for g in GOLDEN["inbox"]])
def test_inbox_count_and_list_give_the_recorded_answers(golden, orm):
    args = golden["args"]
    assert _archive(orm).get_num_faxes(**args) == golden["count"]
    for order, key in ((False, "list"), (True, "list_modem")):
        rows = _archive(orm).list_inbox(index=0, limit=10, order_by_modem=order, **args)
        assert [r["fid"] for r in rows] == golden[key]


def test_inbox_paging_and_dates(backend):
    arc = _archive(backend)
    assert [r["fid"] for r in arc.list_inbox(devices=None, index=0, limit=3)] == [4, 3, 2]
    assert [r["fid"] for r in arc.list_inbox(devices=None, index=1, limit=3)] == [1]
    assert [r["fid"] for r in arc.list_inbox(devices=None, index=-5, limit=3)] == [4, 3, 2]
    assert "m_archstamp" in arc.list_inbox(devices=None, limit=1)[0]


def test_prev_and_next_follow_the_visible_inbox(backend):
    arc = _archive(backend)
    arc.get_num_faxes(devices=["ttyS0", "ttyS1"])
    assert arc.load_fax(3)
    assert (arc.get_fid_prev(), arc.get_fid_next()) == (4, 2)
    assert arc.load_fax(4) and arc.get_fid_prev() is None
    assert arc.load_fax(1) and arc.get_fid_next() is None


# --- loading and changing ------------------------------------------------------------------------------------

def test_load_and_missing(backend):
    arc = _archive(backend)
    assert arc.load_fax(5) and arc.get_fid() == 5 and arc.get_pages() == 1 and arc.get_modemdev() == "ttyS0"
    assert arc.load_fax("5") and arc.get_fid() == 5
    other = _archive(backend)
    assert other.load_fax(999) is False and "didn't load" in other.error
    assert other.load_fax(0) is False


def test_set_category_note_content_numid_company(backend):
    arc = _archive(backend)
    assert arc.load_fax(5)
    assert arc.set_category(2, userid=9) and arc.set_note("hello 'x' \\ 한글", 1, 9)
    assert arc.set_faxcontent("body text") and arc.set_faxnumid(2) and arc.set_companyid(11)
    check = _archive(backend)
    assert check.load_fax(5)
    d = check.dbdata
    assert (d["faxcatid"], d["lastmoduser"], d["description"], d["faxcontent"], d["faxnumid"], d["companyid"]) == (
        1, 9, "hello 'x' \\ 한글", "body text", 2, 11)
    assert d["lastmoddate"]


def test_remove_category_and_reassign_change_many_rows(backend):
    arc = _archive(backend)
    assert arc.remove_category(1) is True
    assert _search(backend, **BASE, sentrecvd="*", superuser=True, category=1)[1] == []
    assert _archive(backend).remove_category(0) is False
    assert arc.reassign(7, 8) is True
    assert _archive(backend).load_fax(7) and _archive(backend).reassign(0, 5) is False
    check = _archive(backend)
    check.load_fax(7)
    assert check.get_companyid() == 8


def test_create_fax_returns_the_new_id_and_stores_a_clean_number(backend):
    arc = _archive(backend)
    assert arc.create_fax("/fax/new", 2, "(555) 123-4567", 3, "2026-04-01 10:00:00", didr_id=4)
    fid = arc.get_fid()
    assert fid and fid > 12
    check = _archive(backend)
    assert check.load_fax(fid)
    assert (check.get_origfaxnum(), check.get_pages(), check.get_didr_id(), check.get_faxnumid()) == ("5551234567", 3, 4, 2)


def test_delete_and_prune(backend, tmp_path):
    arc = _archive(backend)
    assert arc.delete_fax(5) is True and _archive(backend).load_fax(5) is False
    assert _archive(backend).delete_fax(999) is False
    n = _archive(backend).prune_archive(days=1)
    assert n == 11 and _archive(backend).load_fax(12) is False          # every remaining fax is older than a day


def test_inbox_to_archive_helpers(backend):
    from namifax.services.archive_in import ArchiveIn

    arc = ArchiveIn(db=backend)
    assert arc.load_fax(1)
    assert arc.get_inbox() in (1, True)


# --- real servers --------------------------------------------------------------------------------------------

@pytest.mark.serverdb
def test_server_matrix_matches_the_recorded_answers(monkeypatch, server_db_url, alembic_cfg):
    from namifax.models import FaxArchive

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as s:
            _load_session(s)
            for g in GOLDEN["search"] + GOLDEN["paging"]:
                crit = {**BASE, **g["case"]} if g in GOLDEN["search"] else g["case"]
                assert _search(s, **crit) == (g["numrows"], g["fids"]), g["case"]
            for g in GOLDEN["inbox"]:
                args = g["args"]
                assert _archive(s).get_num_faxes(**args) == g["count"]
                for order, key in ((False, "list"), (True, "list_modem")):
                    rows = _archive(s).list_inbox(index=0, limit=10, order_by_modem=order, **args)
                    assert [r["fid"] for r in rows] == g[key], args
            if engine.dialect.name == "postgresql":      # rows with explicit ids do not advance the sequence
                s.execute(text("SELECT setval(pg_get_serial_sequence('\"FaxArchive\"', 'fid'), 12)"))
            arc = _archive(s)
            assert arc.create_fax("/fax/n", 1, "555", 1) and arc.set_note("한글 'q'", 1, 2)
            assert arc.reassign(7, 8) and arc.remove_category(1)
            s.commit()
        with Session(engine) as s:
            assert s.execute(sa.select(sa.func.count()).select_from(FaxArchive)).scalar() == len(ROWS) + 1
    finally:
        engine.dispose()
