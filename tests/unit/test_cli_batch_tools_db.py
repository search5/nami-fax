"""P2: batch tool CLIs live in namifax.cli and use an injected/opened database."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest



def _fake_cli_db(opened, calls):
    @contextmanager
    def fake(*a, **k):
        calls.append(1)
        yield opened
    return fake


# --- import_users ---------------------------------------------------------------

def test_import_users_creates_accounts_in_injected_db(tmp_path, seeded_db):
    from namifax.cli import import_users

    f = tmp_path / "users.txt"
    f.write_text("Eve Doe\teve\tSecret123!\teve@x.test\n")
    assert import_users.main([str(f)], db=seeded_db) == 0
    seeded_db.query("SELECT username FROM UserAccount WHERE username = 'eve'")
    assert seeded_db.get_records() == [{"username": "eve"}]


def test_import_users_usage_and_missing_file_do_not_open_db(tmp_path):
    from namifax.cli import import_users

    with patch.object(import_users, "cli_session", side_effect=AssertionError("must not open DB")):
        assert import_users.main([]) == 0
        assert import_users.main([str(tmp_path / "nope")]) == 1


def test_import_users_opens_one_cli_session(tmp_path):
    from linked_db import close_linked, linked_db
    from namifax.cli import import_users

    f = tmp_path / "users.txt"
    f.write_text("A B\ta1\tSecret123!\ta1@x.test\nC D\tc1\tSecret123!\tc1@x.test\n")
    calls = []
    db, session = linked_db()
    try:
        with patch.object(import_users, "cli_session", _fake_cli_db(session, calls)):
            assert import_users.main([str(f)]) == 0
        assert calls == [1]
        db.query("SELECT username FROM UserAccount WHERE username IN ('a1', 'c1') ORDER BY username")
        assert [r["username"] for r in db.get_records()] == ["a1", "c1"]
    finally:
        close_linked(db, session)


# --- import_blacklist -----------------------------------------------------------

def test_import_blacklist_creates_rules_in_injected_db(tmp_path, seeded_db, capsys):
    from namifax.cli import import_blacklist

    f = tmp_path / "bl.txt"
    f.write_text("5551234\n5559999\n")
    assert import_blacklist.main([str(f), "ttyS0"], db=seeded_db) == 0
    assert "Created 2 rules" in capsys.readouterr().out
    seeded_db.query("SELECT callid FROM DynConf WHERE callid IN ('5551234', '5559999') ORDER BY callid")
    assert [r["callid"] for r in seeded_db.get_records()] == ["5551234", "5559999"]


def test_import_blacklist_usage_does_not_open_db():
    from namifax.cli import import_blacklist

    with patch.object(import_blacklist, "cli_session", side_effect=AssertionError("must not open DB")):
        assert import_blacklist.main([]) == 0


# --- reroute --------------------------------------------------------------------

def test_reroute_updates_modem_contact_through_a_session(app, dbengine, monkeypatch):
    from sqlalchemy.orm import Session

    from namifax.cli import reroute
    from namifax.services.modem import FaxModem

    monkeypatch.delenv("ENABLE_DID_ROUTING", raising=False)
    with Session(dbengine) as session:
        device = FaxModem(db=session).list_all()[0]["device"]
    assert reroute.main([device, "new@x.test"]) == 0
    with Session(dbengine) as session:
        modem = FaxModem(db=session)
        assert modem.load_device(device) and modem.contact == "new@x.test"


def test_reroute_updates_a_did_route_when_did_routing_is_enabled(app, dbengine, monkeypatch):
    from sqlalchemy.orm import Session

    from namifax.cli import reroute
    from namifax.services.did import DIDRouting

    monkeypatch.setenv("ENABLE_DID_ROUTING", "1")
    with Session(dbengine) as session:
        route = DIDRouting(db=session).list_all()[0]["routecode"]
    assert reroute.main([route, "did@x.test"]) == 0
    with Session(dbengine) as session:
        did = DIDRouting(db=session)
        assert did.load_route(route) and did.contact == "did@x.test"


def test_reroute_unknown_device_returns_error(app, monkeypatch, capsys):
    from namifax.cli import reroute

    monkeypatch.delenv("ENABLE_DID_ROUTING", raising=False)
    assert reroute.main(["ttyNOPE", "a@x.test"]) == 1
    assert "Error loading device" in capsys.readouterr().out


def test_reroute_usage_does_not_open_db():
    from namifax.cli import reroute

    with patch.object(reroute, "cli_session", side_effect=AssertionError("must not open DB")):
        assert reroute.main(["only-one"]) == 0


# --- ocr_import / create_thumbnails ---------------------------------------------

def test_ocr_import_disabled_does_not_open_db(capsys):
    from namifax.cli import ocr_import

    with patch.object(ocr_import, "ENABLE_OCR_SUPPORT", False), \
            patch.object(ocr_import, "cli_session", side_effect=AssertionError("must not open DB")):
        assert ocr_import.main([]) == 0
    assert "ENABLE_OCR_SUPPORT" in capsys.readouterr().out


def test_ocr_import_passes_db_to_archive_and_uses_real_ocr_helper():
    from namifax.cli import ocr_import

    db = object()
    arc = MagicMock(name="FaxPDFArchive")
    arc.return_value.search_archive.return_value = 1
    arc.return_value.next_archive_entry.side_effect = [5, None]
    arc.return_value.load_fax.return_value = True
    arc.return_value.get_tiffpath.return_value = "/tmp/f.tif"
    with patch.object(ocr_import, "ENABLE_OCR_SUPPORT", True), patch.object(ocr_import, "FaxPDFArchive", arc), \
            patch.object(ocr_import, "ocr_faxcontent", return_value="hello"):
        assert ocr_import.main([], db=db) == 0
    assert arc.call_args.kwargs.get("db") is db
    arc.return_value.set_faxcontent.assert_called_once_with("hello")


def test_create_thumbnails_passes_db_to_both_archives():
    from namifax.cli import create_thumbnails

    db = object()
    arc = MagicMock(name="FaxPDFArchive")
    arc.return_value.search_archive.return_value = 0
    with patch.object(create_thumbnails, "FaxPDFArchive", arc):
        assert create_thumbnails.main([], db=db) == 0
    assert arc.call_args_list and all(c.kwargs.get("db") is db for c in arc.call_args_list)


def test_create_thumbnails_opens_cli_db():
    from namifax.cli import create_thumbnails

    opened, calls = object(), []
    arc = MagicMock(name="FaxPDFArchive")
    arc.return_value.search_archive.return_value = 0
    with patch.object(create_thumbnails, "cli_session", _fake_cli_db(opened, calls)), \
            patch.object(create_thumbnails, "FaxPDFArchive", arc):
        create_thumbnails.main([])
    assert calls == [1] and arc.call_args.kwargs.get("db") is opened


# --- main.py wiring -------------------------------------------------------------

@pytest.mark.parametrize("cmd,mod", [
    ("ocr-import", "ocr_import"), ("create-thumbnails", "create_thumbnails"),
    ("import-users", "import_users"), ("import-blacklist", "import_blacklist"), ("reroute", "reroute"),
])
def test_main_dispatches_to_namifax_cli_modules(cmd, mod):
    import importlib

    main_mod = importlib.import_module("namifax.main")  # `namifax.main` is also a function name in the package
    target = importlib.import_module(f"namifax.cli.{mod}")
    with patch.object(target, "main", return_value=0) as m:
        assert main_mod.main([cmd, "x"]) == 0
    m.assert_called_once_with(["x"])
