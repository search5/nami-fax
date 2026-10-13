"""Received faxes are printed when PRINTFAXRCVD is on (the original faxrcvd's PRINTING SUPPORT): fax2ps | lpr for the TIFF, or the
PDF straight to lpr, to the printer the routing chose."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from namifax.services import printing


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("PRINTFAXRCVD", "FAXRCVD_PRINT_PDF", "PRINTCMD", "PRINTFAX2PS", "PDFPRINTCMD"):
        monkeypatch.delenv(name, raising=False)


def test_printing_is_off_by_default():
    assert printing.enabled() is False


def test_nothing_is_run_when_it_is_off():
    with patch("subprocess.Popen") as popen, patch("subprocess.run") as run:
        assert printing.print_received("/f/fax.tif", "/f/fax.pdf", "office") is False
    assert not popen.called and not run.called


def test_the_tiff_goes_through_fax2ps_to_the_printer(monkeypatch):
    monkeypatch.setenv("PRINTFAXRCVD", "1")
    first, second = MagicMock(), MagicMock()
    first.stdout = object()
    first.wait.return_value = 0
    second.wait.return_value = 0
    second.returncode = 0
    with patch("subprocess.Popen", side_effect=[first, second]) as popen:
        assert printing.print_received("/f/fax.tif", "/f/fax.pdf", "office") is True
    assert popen.call_args_list[0].args[0] == ["/usr/bin/fax2ps", "/f/fax.tif"]
    assert popen.call_args_list[1].args[0] == ["/usr/bin/lpr", "-P", "office"]


def test_no_printer_name_means_the_default_printer(monkeypatch):
    monkeypatch.setenv("PRINTFAXRCVD", "1")
    proc = MagicMock(returncode=0)
    proc.wait.return_value = 0
    with patch("subprocess.Popen", return_value=proc) as popen:
        printing.print_received("/f/fax.tif", "/f/fax.pdf", "")
    assert popen.call_args_list[1].args[0] == ["/usr/bin/lpr"]


def test_the_pdf_can_be_printed_instead(monkeypatch):
    monkeypatch.setenv("PRINTFAXRCVD", "1")
    monkeypatch.setenv("FAXRCVD_PRINT_PDF", "1")
    monkeypatch.setenv("PDFPRINTCMD", "/usr/bin/lp")
    with patch("subprocess.run", return_value=MagicMock(returncode=0)) as run:
        assert printing.print_received("/f/fax.tif", "/f/fax.pdf", "office") is True
    assert run.call_args.args[0] == ["/usr/bin/lp", "-P", "office", "/f/fax.pdf"]


def test_a_printer_name_cannot_inject_options_or_shell(monkeypatch):
    monkeypatch.setenv("PRINTFAXRCVD", "1")
    monkeypatch.setenv("FAXRCVD_PRINT_PDF", "1")
    with patch("subprocess.run", return_value=MagicMock(returncode=0)) as run:
        printing.print_received("/f/fax.tif", "/f/fax.pdf", "x; rm -rf /")
    assert run.call_args.args[0][-3:] == ["-P", "x; rm -rf /", "/f/fax.pdf"] and run.call_args.kwargs.get("shell") in (None, False)


def test_a_missing_program_is_reported_not_raised(monkeypatch):
    monkeypatch.setenv("PRINTFAXRCVD", "1")
    monkeypatch.setenv("FAXRCVD_PRINT_PDF", "1")
    with patch("subprocess.run", side_effect=FileNotFoundError("lpr")):
        assert printing.print_received("/f/fax.tif", "/f/fax.pdf", "") is False


# --- in the hook --------------------------------------------------------------------------------------------------------------

from namifax.cli import faxrcvd as hook  # noqa: E402


def _hook(tmp_path, *, printer_of_modem=None, contact=None, book_printer=None):
    tiff = tmp_path / "fax00123.tif"
    tiff.write_bytes(b"mock tiff")
    modem = MagicMock()
    modem.get_printer.return_value = printer_of_modem
    modem.get_contact.return_value = contact
    modem.get_faxcatid.return_value = None
    book = MagicMock()
    book.find_or_create_number.return_value = (1, 1, "found")
    book.get_printer.return_value = book_printer
    book.get_category.return_value = None
    book.get_email.return_value = None
    inbox = MagicMock()
    inbox.create.return_value = True
    inbox.get_fid.return_value = 7
    with patch.multiple(hook, FaxModem=MagicMock(return_value=modem), NFAddressBook=MagicMock(return_value=book),
                        ArchiveIn=MagicMock(return_value=inbox), DIDRouting=MagicMock(), BarcodeRouting=MagicMock()), \
            patch.object(hook, "faxinfo", return_value={"Sender": "1", "Pages": "1", "Received": "2026:10:01 10:00:00"}), \
            patch.object(hook, "tiff2pdf"), patch.object(hook, "copy_tiff", return_value=True), patch.object(hook, "static_preview"), patch.object(hook, "send_mail"), \
            patch.object(hook, "bardecode", return_value=None), patch("namifax.services.ocr.OcrService"), \
            patch.object(hook, "print_received") as printed:
        hook.run_faxrcvd(["faxrcvd.py", str(tiff), "ttyS0", "comm01", "none"], session=object())
    return printed, inbox


def test_the_hook_prints_on_the_printer_the_routing_chose(tmp_path, monkeypatch):
    monkeypatch.setenv("PRINTFAXRCVD", "1")
    printed, _ = _hook(tmp_path, printer_of_modem="lobby")
    assert printed.call_args.args[2] == "lobby" and printed.call_args.args[0].endswith("fax00123.tif")


def test_a_printer_from_the_address_book_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("PRINTFAXRCVD", "1")
    printed, _ = _hook(tmp_path, printer_of_modem="lobby", book_printer="accounting")
    assert printed.call_args.args[2] == "accounting"


def test_a_fax_printed_for_fax2email_is_archived_when_asked(tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "ARCHIVEFAX2EMAIL", True)
    monkeypatch.setenv("PRINTFAXRCVD", "1")
    printed, inbox = _hook(tmp_path, book_printer="accounting")
    inbox.set_archivebox.assert_called_with(7)
