#!/usr/bin/env python3
"""AvantFAX modern CLI replacement for includes/faxrcvd.php.

Handles HylaFAX inbound fax processing, TIFF inspection, PDF conversion,
thumbnail generation, address book auto-registration, routing resolution,
and notification email/print dispatch.
"""

from __future__ import annotations

import datetime
import os
import re
import shutil
import sys
from typing import Any, Sequence

# Ensure src directory is on sys.path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from namifax.common import settings
from namifax.services import printing
from namifax.services.printing import print_received
from namifax.common.helpers import (
    annotate_fax,
    copy_tiff,
    hylafax_date_to_iso,
    avantfaxlog,
    bardecode,
    clean_faxnum,
    faxinfo,
    get_admin_email,
    mkdirs,
    ocr_faxcontent,
    send_mail,
    static_preview,
    tiff2pdf,
)
from namifax.db.provider import cli_session, use_session
from namifax.services.addressbook import NFAddressBook
from namifax.services.archive_in import ArchiveIn
from namifax.services.barcode import BarcodeRouting
from namifax.services.cloud_storage import upload_received_fax
from namifax.services.did import DIDRouting
from namifax.services.modem import FaxModem

ARCHIVE = settings.archive_dir()
ENABLE_DID_ROUTING = os.environ.get("ENABLE_DID_ROUTING", "0") in ("1", "true", "True")
AUTOCONFDID = settings.flag("AUTOCONFDID", True)
ENABLE_FAX_ANNOTATION = os.environ.get("ENABLE_FAX_ANNOTATION", "0") in ("1", "true", "True")
FAXRCVD_INCLUDE_THUMBNAIL = os.environ.get("FAXRCVD_INCLUDE_THUMBNAIL", "1") in ("1", "true", "True")
FAXRCVD_INCLUDE_PDF = settings.flag("FAXRCVD_INCLUDE_PDF", True)
ARCHIVEFAX2EMAIL = settings.flag("ARCHIVEFAX2EMAIL", True)
TIFF_TO_G4 = settings.flag("TIFF_TO_G4", False)
ENABLE_FAX_ANNOTATION = settings.flag("ENABLE_FAX_ANNOTATION", False)
ANN_GRAVITY = settings.text("ANN_GRAVITY", "southeast")
PRINTFAXRCVD = os.environ.get("PRINTFAXRCVD", "0") in ("1", "true", "True")
PRINTERNAME = os.environ.get("PRINTERNAME", "")

LANG = {
    "FROM": "From",
    "PN_PAGES": "Pages",
    "COMPANY_EXISTS": "Company already exists",
}


def caller_from(finfo: dict, cid_number: str, cid_name: str, did_num: str) -> tuple[str, str, str]:
    """The caller number, name and dialled number: what the command line gave, else the CallID lines the settings point at."""
    def line(kind: str) -> str:
        value = finfo.get(f"CallID{settings.callid_index(kind)}")
        return value if value and value != "<NONE>" else ""

    return cid_number or line("CIDNumber"), cid_name or line("CIDName"), did_num or line("DIDNum")


def ocr_wanted() -> bool:
    return settings.ocr_enabled()


def run_faxrcvd(argv: Sequence[str] | None = None, *, session: Any = None) -> int:
    """Execute HylaFAX inbound fax received handler.

    Everything runs in one ORM ``session``: the one passed in, or else one opened on the configured
    database (committed when the hook finishes, rolled back on error).
    """
    args = list(argv) if argv is not None else list(sys.argv)

    if len(args) < 3:
        print("Usage: faxrcvd.php file devID commID error-msg [CIDNumber] [CIDName] [DIDnum]")
        return 0

    if session is not None:
        with use_session(session):
            return _process_faxrcvd(args, session)
    with cli_session(ensure_schema=True) as opened:
        return _process_faxrcvd(args, opened)


def _process_faxrcvd(args: list[str], session: Any) -> int:
    """Process one received fax using the given database session."""

    tiff_file = args[1]
    modemdev = args[2]
    comm_id = args[3] if len(args) >= 4 else ""
    error_msg = args[4] if len(args) >= 5 else ""
    cid_number = args[5] if len(args) >= 6 else None
    cid_name = args[6] if len(args) >= 7 else None
    did_num = args[7] if len(args) >= 8 else None

    # Check / configure modem
    modem = FaxModem(db=session)
    if not modem.load_device(modemdev):
        avantfaxlog(f"faxrcvd> Found unconfigured modem: {modemdev}. Configuring...", echo=False)
        modem.create(modemdev, modemdev, None)

    # Process TIFF file
    if not os.path.exists(tiff_file):
        avantfaxlog(f"faxrcvd> failed: {tiff_file} not found", echo=False)
        return 0

    finfo = faxinfo(tiff_file)
    if not finfo:
        avantfaxlog(f"faxrcvd> failed: {tiff_file} {modemdev} corrupted", echo=False)
        return 0

    sender = finfo.get("Sender", "")
    pages = int(finfo.get("Pages", 1))
    recv_date = finfo.get("Received", datetime.datetime.now().strftime("%Y:%m:%d %H:%M:%S"))

    cid_number, cid_name, did_num = caller_from(finfo, cid_number, cid_name, did_num)

    company_name = cid_name if cid_name else sender
    company_fax = cid_number if cid_number else sender

    avantfaxlog(
        f"faxrcvd> executing: {tiff_file} {modemdev} '{comm_id}' '{error_msg}' CIDNum: '{cid_number}' CIDName: '{cid_name}' DID: '{did_num}'",
        echo=False,
    )
    avantfaxlog(f"faxrcvd> PROCESSING FAX from '{company_fax}' ({pages} pages) received '{recv_date}'", echo=False)

    # Prepare archive directory
    parts = recv_date.split(" ", 1)
    day = parts[0].replace(":", os.sep) if parts else "date"
    hour = parts[1] if len(parts) > 1 else "00:00:00"

    hylfaxid = os.path.basename(tiff_file).replace("fax", "").replace(".tif", "")
    clean_num = re.sub(r"\+", "", clean_faxnum(company_fax)) or "unknown"
    faxpath = os.path.join(ARCHIVE, day, clean_num, hylfaxid)
    mkdirs(faxpath)

    faxfile = os.path.join(faxpath, "fax.tif")
    pdffile = os.path.join(faxpath, "fax.pdf")
    thumbnail = os.path.join(faxpath, "thumb.png")

    if not copy_tiff(tiff_file, faxfile, group4=TIFF_TO_G4):
        avantfaxlog(f"faxrcvd> Failed to copy {tiff_file} to {faxfile}", echo=True)
        return 0

    print("Create PDF")
    tiff2pdf(faxfile, pdffile)

    print("Create Thumbnails")
    static_preview(faxpath, pages)

    # AddressBook
    # (loadbyfaxnum() answers with a tuple, which is always true: new senders were never registered)
    addressbook = NFAddressBook(db=session)
    faxnumid, _company_id, outcome = addressbook.find_or_create_number(company_fax, company_name)
    if outcome == "multiple":
        print("WARNING: Multiple results for faxnumber")
    elif outcome in ("found", "created", "company_exists"):
        addressbook.inc_faxfrom()
        if outcome != "found":
            avantfaxlog(f"faxrcvd> Created fax number '{company_fax}' for company '{company_name}'", echo=False)
    else:
        avantfaxlog(f"faxrcvd> Couldn't register fax number '{company_fax}': {addressbook.get_error()}", echo=False)

    # DID Routing
    didr_id = 0
    didr = DIDRouting(db=session)
    if ENABLE_DID_ROUTING and did_num:
        if didr.load_route(did_num):
            didr_id = didr.get_didr_id()
        elif AUTOCONFDID:
            if didr.create(did_num, did_num, None):
                didr_id = didr.get_didr_id()

    # ArchiveIn
    inbox = ArchiveIn(db=session)
    faxid = None
    if inbox.create(faxpath, faxnumid, company_fax, modemdev, pages, hylafax_date_to_iso(recv_date), didr_id):
        faxid = inbox.get_fid()
        avantfaxlog(f"faxrcvd> Inserted {faxpath} from {company_name} to Inbox", echo=False)
        if ENABLE_FAX_ANNOTATION:                                       # the fax id on every page of the PDF
            annotate_fax(faxfile, f"FaxID: {faxid}", pdffile, gravity=ANN_GRAVITY)
        ocr_txt = ocr_faxcontent(faxfile)                               # read the fax once; the text goes to both places
        if ocr_txt:
            inbox.set_faxcontent(ocr_txt)
            try:
                from namifax.services.ocr import OcrService

                ocr_index = OcrService(db=session)
                with session.begin_nested():                            # a failed index must not undo the inbox row
                    ocr_index.store_text(os.path.basename(faxfile), ocr_txt, int(pages or 1), faxid)
            except Exception as e:
                avantfaxlog(f"faxrcvd> OCR indexing failed for {faxfile}: {e}", echo=False)
        upload_received_fax(session, faxid, faxpath)                    # S3 only; a failure is just logged

    # Routing Priorities: DID/Modem -> Fax2Email -> Barcode
    printer = PRINTERNAME
    printer_type = "SYS"
    email_recipient = None
    email_type = None
    faxcatid = None
    category_type = None

    if not ENABLE_DID_ROUTING:
        faxcatid = modem.get_faxcatid()
        if faxcatid:
            category_type = "MODEM"
        printer = modem.get_printer() or printer
        if printer != PRINTERNAME:
            printer_type = "MODEM"
        email_recipient = modem.get_contact()
        if email_recipient:
            email_type = "MODEM"
    elif didr_id:
        faxcatid = didr.get_faxcatid()
        if faxcatid:
            category_type = "DID"
        printer = didr.get_printer() or printer
        if printer != PRINTERNAME:
            printer_type = "DID"
        email_recipient = didr.get_contact()
        if email_recipient:
            email_type = "DID"

    # Fax2Email
    if addressbook.get_category():
        faxcatid = addressbook.get_category()
        category_type = "Fax2Email"
    if addressbook.get_printer():
        printer = addressbook.get_printer()
        printer_type = "Fax2Email"
    if addressbook.get_email():
        email_recipient = addressbook.get_email()
        email_type = "Fax2Email"

    # Barcode
    bcode_val = bardecode(faxfile)
    if bcode_val:
        inbox.set_note(bcode_val, None, None)
        barcode = BarcodeRouting(db=session)
        if barcode.load_route(bcode_val):
            if barcode.get_faxcatid():
                faxcatid = barcode.get_faxcatid()
                category_type = "BARCODE"
            if barcode.get_printer():
                printer = barcode.get_printer()
                printer_type = "BARCODE"
            if barcode.get_contact():
                email_recipient = barcode.get_contact()
                email_type = "BARCODE"

    # Category
    if faxcatid:
        print(f"Setting {category_type} category id {faxcatid}")
        inbox.set_category(faxcatid)

    # Email notification
    company = addressbook.get_company() or company_name
    from_email = get_admin_email()
    now_str = datetime.datetime.now().strftime(settings.email_date_format())
    subject = f"fax: {company} {now_str}"
    text = f"{LANG['FROM']}: {company}"

    desc = addressbook.get_description()
    if desc:
        text += f" ({desc})\n"
    text += f"\nfax id: {faxid}\n{LANG['PN_PAGES']}: {pages}\n"

    thumb_att = thumbnail if FAXRCVD_INCLUDE_THUMBNAIL else None
    pdf_att = pdffile if FAXRCVD_INCLUDE_PDF else None

    if email_recipient:
        if email_type == "Fax2Email" and ARCHIVEFAX2EMAIL and faxid:
            print("Archiving fax")
            inbox.set_archivebox(faxid)
        if send_mail(email_recipient, from_email, subject, text, file=pdf_att, embedd=thumb_att):
            avantfaxlog(f"faxrcvd> Fax sent to {email_type} contact {email_recipient}", echo=False)

    # Printing support
    if printing.enabled():
        avantfaxlog(f"faxrcvd> Sending fax to {printer_type} printer {printer}", echo=True)
        print_received(tiff_file, pdffile, printer)
        if printer_type == "Fax2Email" and ARCHIVEFAX2EMAIL and faxid:
            print("Archiving fax")
            inbox.set_archivebox(faxid)

    return 0


def main() -> None:
    code = run_faxrcvd()
    sys.exit(code)


if __name__ == "__main__":
    main()
