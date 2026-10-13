"""Spec 48 loop C4: dynconf, phb, createuser and faxcover CLIs use an injected/opened database."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

from namifax.cli import dynconf as dynconf_mod
from namifax.cli import faxcover as faxcover_mod
from namifax.cli import phb as phb_mod
from namifax.cli import user as user_mod


def _fake_cli_db(opened, calls):
    @contextmanager
    def fake(*a, **k):
        calls.append(1)
        yield opened
    return fake


# --- dynconf --------------------------------------------------------------------

def test_dynconf_injected_db():
    db = object()
    with patch.object(dynconf_mod, "DynamicConfig") as cls:
        cls.return_value.lookup.return_value = False
        assert dynconf_mod.run_dynconf(["dynconf.py", "ttyS0", "12345"], db=db) == 0
    assert cls.call_args.kwargs.get("db") is db


def test_dynconf_opens_cli_db_and_usage_does_not():
    opened, calls = object(), []
    with patch.object(dynconf_mod, "cli_session", _fake_cli_db(opened, calls)), \
            patch.object(dynconf_mod, "DynamicConfig") as cls:
        cls.return_value.lookup.return_value = False
        dynconf_mod.run_dynconf(["dynconf.py", "ttyS0", "12345"])
        assert cls.call_args.kwargs.get("db") is opened and calls == [1]
        dynconf_mod.run_dynconf(["dynconf.py"])
    assert calls == [1]


# --- phb ------------------------------------------------------------------------

def test_phb_injected_db(tmp_path):
    db = object()
    with patch.object(phb_mod, "NFAddressBook") as cls, \
            patch.object(phb_mod, "generate_phonebook_content", return_value="x"):
        assert phb_mod.run_phb(["phb", "-o", str(tmp_path / "pb")], db=db) == 0
    assert cls.call_args.kwargs.get("db") is db


def test_phb_opens_cli_db(tmp_path):
    opened, calls = object(), []
    with patch.object(phb_mod, "cli_session", _fake_cli_db(opened, calls)), \
            patch.object(phb_mod, "NFAddressBook") as cls, \
            patch.object(phb_mod, "generate_phonebook_content", return_value="x"):
        phb_mod.run_phb(["phb", "-o", str(tmp_path / "pb")])
    assert cls.call_args.kwargs.get("db") is opened and calls == [1]


# --- createuser -----------------------------------------------------------------

def test_createuser_creates_account_in_injected_db(seeded_db):
    code = user_mod.run_createuser(["-u", "carol", "-p", "Secret123!", "-e", "c@x.test", "-n", "Carol"], session=seeded_db)
    assert code == 0
    seeded_db.query("SELECT username FROM UserAccount WHERE username = 'carol'")
    assert seeded_db.get_records() == [{"username": "carol"}]


def test_createuser_opens_one_cli_session():
    from sqlsession import seeded_session

    calls = []
    session = seeded_session()
    try:
        with patch.object(user_mod, "cli_session", _fake_cli_db(session, calls)):
            assert user_mod.run_createuser(["-u", "dave", "-p", "Secret123!", "-e", "d@x.test"]) == 0
        assert calls == [1]
        session.query("SELECT username, is_admin FROM UserAccount WHERE username = 'dave'")
        assert session.get_records() == [{"username": "dave", "is_admin": 1}]
    finally:
        session.disconnect()


# --- faxcover -------------------------------------------------------------------

def _cover(tmp_path, argv, **kwargs):
    tpl = tmp_path / "cover.ps"
    tpl.write_text("x")
    with patch.object(faxcover_mod, "process_template", return_value=[]) as proc, \
            patch.object(faxcover_mod, "avantfaxlog"):
        code = faxcover_mod.run_faxcover(["faxcover", *argv, "-C", str(tpl)], **kwargs)
    assert code == 0
    return proc.call_args.args[2]


def test_faxcover_resolves_sender_from_username_in_injected_db(tmp_path, seeded_db):
    values = _cover(tmp_path, ["-f", "operator", "-n", "555"], db=seeded_db)
    assert values["from"] == "Operator User"
    assert values["from-mail-address"] == "operator@namifax.local"


def test_faxcover_resolves_sender_name_from_email_in_injected_db(tmp_path, seeded_db):
    values = _cover(tmp_path, ["-f", "x", "-M", "admin@namifax.local", "-n", "555"], db=seeded_db)
    assert values["from"] == "System Administrator"


def test_faxcover_opens_a_cli_session_only_when_required_args_present(tmp_path, seeded_db):
    calls = []
    with patch.object(faxcover_mod, "cli_session", _fake_cli_db(seeded_db, calls)):
        _cover(tmp_path, ["-f", "operator", "-n", "555"])
        assert calls == [1]
        assert faxcover_mod.run_faxcover(["faxcover"]) == 0
    assert calls == [1]
