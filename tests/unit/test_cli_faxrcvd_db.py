"""Spec 48 loop C1: faxrcvd CLI builds every domain object from one injected/opened database."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from namifax.cli import faxrcvd as mod


def _run(tmp_path, **kwargs):
    tiff = tmp_path / "fax00123.tif"
    tiff.write_bytes(b"mock tiff")
    classes = {n: MagicMock(name=n) for n in ("FaxModem", "NFAddressBook", "ArchiveIn", "DIDRouting", "BarcodeRouting")}
    classes["NFAddressBook"].return_value.find_or_create_number.return_value = (1, 1, "found")
    classes["ArchiveIn"].return_value.create.return_value = True
    classes["ArchiveIn"].return_value.get_fid.return_value = 7
    with patch.dict("os.environ", {"ENABLE_OCR_SUPPORT": "1"}), patch.multiple(mod, **classes), \
            patch.object(mod, "faxinfo", return_value={"Sender": "1", "Pages": "1", "Received": "2026:10:01 10:00:00"}), \
            patch.object(mod, "tiff2pdf"), patch.object(mod, "copy_tiff", return_value=True), patch.object(mod, "static_preview"), patch.object(mod, "send_mail"), \
            patch.object(mod, "bardecode", return_value=None), patch.object(mod, "ocr_faxcontent", return_value="text"):
        code = mod.run_faxrcvd(["faxrcvd.py", str(tiff), "ttyS0", "comm01", "none"], **kwargs)
    return code, classes


def test_every_service_gets_the_one_session(tmp_path):
    """Modems, DID routes, the address book and the archive (with its OCR text) all run in the same ORM session."""
    session = object()
    code, classes = _run(tmp_path, session=session)
    assert code == 0
    for name in ("FaxModem", "DIDRouting", "NFAddressBook", "ArchiveIn"):
        assert classes[name].call_args_list, f"{name} not built"
        assert all(c.kwargs.get("db") is session for c in classes[name].call_args_list), name
    classes["ArchiveIn"].return_value.set_faxcontent.assert_called_once_with("text")


def test_without_injection_one_cli_session_is_opened(tmp_path):
    session, calls = object(), []

    @contextmanager
    def fake_cli_session(*a, **k):
        calls.append(1)
        yield session

    with patch.object(mod, "cli_session", fake_cli_session):
        code, classes = _run(tmp_path)
    assert code == 0 and calls == [1]
    assert classes["FaxModem"].call_args.kwargs.get("db") is session
    assert classes["ArchiveIn"].call_args.kwargs.get("db") is session


def test_usage_does_not_open_a_database():
    with patch.object(mod, "cli_session", side_effect=AssertionError("must not open DB for usage")):
        assert mod.run_faxrcvd(["faxrcvd.py"]) == 0


def test_an_unconfigured_modem_is_registered_and_logged_in_the_configured_database(app, dbengine, tmp_path):
    """End to end: the hook runs on its own connection, commits, and the web side sees the result."""
    from sqlalchemy.orm import Session

    from namifax.services.modem import FaxModem
    from namifax.services.syslog import SysLogService

    missing = tmp_path / "gone.tif"
    assert mod.run_faxrcvd(["faxrcvd.py", str(missing), "ttyS5", "comm1", "none"]) == 0
    with Session(dbengine) as session:
        assert FaxModem(db=session).load_device("ttyS5") is True
        assert any("not found" in r["logtext"] for r in SysLogService(session).search(kw="gone.tif"))
