"""Spec 48 loop C2: notify CLI builds every domain object from one injected/opened database."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from namifax.cli import notify as mod

QFILE = (
    "totpages:2\nstatus:Normal\nexternal:12345678\njobid:999\nmailaddr:test@example.com\n"
    "owner:admin\ncompany:Acme Corp\nregarding:Docs\npostscript:0:0:/tmp/doc.ps\n"
)


def _run(tmp_path, **kwargs):
    qfile = tmp_path / "q1"
    qfile.write_text(QFILE)
    classes = {n: MagicMock(name=n) for n in ("NFAddressBook", "NFUserAccount", "ArchiveOut")}
    ab = classes["NFAddressBook"].return_value
    ab.find_or_create_number.return_value = (1, 10, "created")
    ab.create.return_value = True
    ab.create_faxnumid.return_value = True
    ab.get_companyid.return_value = 10
    ab.get_company.return_value = "Acme Corp"
    ab.get_description.return_value = ""
    user = classes["NFUserAccount"].return_value
    user.load_username.return_value = True
    user.email, user.language = "admin@example.com", "en"
    user.get_uid.return_value = 1
    classes["ArchiveOut"].return_value.create.return_value = True
    classes["ArchiveOut"].return_value.get_fid.return_value = 42
    with patch.multiple(mod, **classes), patch.object(mod, "send_mail"), \
            patch.object(mod, "convert2pdf", return_value=True), patch.object(mod, "pdf_preview"):
        code = mod.run_notify(["notify.py", str(qfile), "done", "00:01:23"], **kwargs)
    return code, classes


def test_every_service_gets_the_one_session(tmp_path):
    session = object()
    code, classes = _run(tmp_path, session=session)
    assert code == 0
    for name in ("NFAddressBook", "NFUserAccount", "ArchiveOut"):
        assert classes[name].call_args_list, f"{name} not built"
        assert all(c.kwargs.get("db") is session for c in classes[name].call_args_list), name


def test_without_injection_one_cli_session_is_opened(tmp_path):
    session, calls = object(), []

    @contextmanager
    def fake_cli_session(*a, **k):
        calls.append(1)
        yield session

    with patch.object(mod, "cli_session", fake_cli_session):
        code, classes = _run(tmp_path)
    assert code == 0 and calls == [1]
    assert classes["NFAddressBook"].call_args.kwargs.get("db") is session
    assert classes["NFUserAccount"].call_args.kwargs.get("db") is session


def test_usage_and_missing_qfile_do_not_open_a_database(tmp_path):
    with patch.object(mod, "cli_session", side_effect=AssertionError("must not open DB")):
        assert mod.run_notify(["notify.py"]) == 0
        assert mod.run_notify(["notify.py", str(tmp_path / "nope"), "done"]) == 0
