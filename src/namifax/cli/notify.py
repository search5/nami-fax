#!/usr/bin/env python3
"""AvantFAX modern CLI replacement for includes/notify.php.

Handles HylaFAX post-send notifications, qfile processing, address book updates,
outbound fax archiving, and email notifications.
"""

from __future__ import annotations

import datetime
import os
import re
import sys
from typing import Any, Sequence

# Ensure src directory is on sys.path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from namifax.common.helpers import (
    avantfaxlog,
    clean_faxnum,
    convert2pdf,
    decode_entity,
    get_admin_email,
    mkdirs,
    pdf_preview,
    send_mail,
)
from namifax.db.provider import cli_session, use_session
from namifax.services.addressbook import NFAddressBook
from namifax.common import settings
from namifax.services.archive_out import ArchiveOut
from namifax.services.user_account import NFUserAccount

FAXMAILUSER = os.environ.get("FAXMAILUSER", "faxmail")
WWWUSER = os.environ.get("WWWUSER", "www-data")      # (the original says "apache"; this is the Debian/Ubuntu web user)
ARCHIVE_SENT = settings.sent_dir()
TMPDIR = os.environ.get("AVANTFAX_TMPDIR", "/tmp/avantfax/")
NOTIFY_ON_SUCCESS = os.environ.get("NOTIFY_ON_SUCCESS", "1") in ("1", "true", "True")
NOTIFY_INCLUDE_PDF = os.environ.get("NOTIFY_INCLUDE_PDF", "0") in ("1", "true", "True")

LANG = {
    "TO": "To",
    "FAX_FAILED": "Fax transmission failed",
    "PN_PAGES": "Pages",
    "FAX_WHY": {
        "done": "Done",
        "blocked": "Blocked",
        "requeued": "Requeued",
        "format_failed": "Format Failed",
        "no_formatter": "No Formatter",
        "poll_no_document": "Poll No Document",
        "killed": "Killed",
        "rejected": "Rejected",
        "removed": "Removed",
        "timedout": "Timed Out",
        "poll_rejected": "Poll Rejected",
        "poll_failed": "Poll Failed",
    },
}


def run_notify(argv: Sequence[str] | None = None, *, session: Any = None) -> int:
    """Execute HylaFAX notification handler.

    Everything runs in one ORM ``session``: the one passed in, or else one opened on the configured database.
    """
    args = list(argv) if argv is not None else list(sys.argv)

    if len(args) < 3:
        print("Usage: notify.php qfile why jobtime [nextTry]")
        return 0

    if not os.path.exists(args[1]):
        print(f"{args[1]} doesn't exist")
        return 0

    if session is not None:
        with use_session(session):
            return _process_notify(args, session)
    with cli_session(ensure_schema=True) as opened:
        return _process_notify(args, opened)


def _process_notify(args: list[str], session: Any) -> int:
    """Process one HylaFAX notification with the given ORM session."""
    qfile = args[1]
    why = args[2]
    jobtime = args[3] if len(args) >= 4 else None
    next_try = args[4] if len(args) >= 5 else None

    avantfaxlog(f"notify> Executing: {qfile} {why} {jobtime} {next_try} ({len(args)})", echo=False)

    faxdone = (why == "done")
    alert = (why in ("blocked", "requeued"))
    fatal = (not faxdone and not alert)

    # Parse qfile
    totpages = "0"
    status = ""
    external = ""
    jobid = ""
    mailaddr = ""
    groupid = ""
    to_location = None
    to_voice = None
    to_person = None
    to_company = None
    regarding = None
    owner = ""
    faxfiles: list[str] = []

    try:
        with open(qfile, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(":", 3)
                key = parts[0]
                val = parts[1] if len(parts) > 1 else ""

                if key == "totpages":
                    totpages = val
                    print(f"totpages: {totpages}")
                elif key == "status":
                    status = val
                    print(f"status: {status}")
                elif key == "external":
                    external = clean_faxnum(val)
                    print(f"external: {external}")
                elif key == "jobid":
                    jobid = val
                    print(f"jobid: {jobid}")
                elif key == "mailaddr":
                    mailaddr = val
                    print(f"mailaddr: {mailaddr}")
                elif key == "groupid":
                    groupid = val
                    print(f"groupid: {groupid}")
                elif key == "location":
                    to_location = val or None
                    print(f"location: {to_location}")
                elif key == "voice":
                    to_voice = val or None
                    print(f"voice: {to_voice}")
                elif key == "receiver":
                    to_person = val or None
                    print(f"receiver: {to_person}")
                elif key == "company":
                    to_company = val or None
                    print(f"company: {to_company}")
                elif key == "regarding":
                    regarding = val or None
                    print(f"regarding: {regarding}")
                elif key == "owner":
                    owner = val.lower()
                    print(f"owner: {owner}")
                elif re.search(r"postscript|pdf|tiff", key):
                    target_file = parts[3] if len(parts) > 3 else ""
                    print(f"Found file: {target_file}")
                    if ";" not in target_file and target_file:
                        faxfiles.append(target_file)
    except OSError as err:
        print(f"Error reading {qfile}: {err}")
        return 0

    if not to_company:
        to_company = external

    # AddressBook lookup & creation: the receiver is registered when the number is new (the original notify.php)
    addressbook = NFAddressBook(db=session)
    faxnumid, cid, outcome = addressbook.find_or_create_number(external, to_company)
    cid = cid or 0
    if outcome == "multiple":
        avantfaxlog("notify> Found fax number with multiple companies", echo=False)
    elif outcome in ("created", "company_exists"):
        addressbook.save_settings({
            "description": None,
            "faxcatid": None,
            "to_person": to_person,
            "to_location": to_location,
            "to_voicenumber": to_voice,
        })
        addressbook.inc_faxto()
        avantfaxlog(f"notify> Created company '{external}' with cid '{cid}'", echo=False)
    elif outcome == "found":
        addressbook.inc_faxto()
    else:
        cid = 0
        avantfaxlog(f"notify> FAILED to register '{external}': {addressbook.get_error()}", echo=False)

    # Sender lookup
    from_email = get_admin_email()
    user = NFUserAccount(db=session)
    user_id = 0
    to_email = mailaddr

    if owner in (FAXMAILUSER, WWWUSER):
        if user.loadbyemail(mailaddr):
            owner = user.username
            to_email = user.email
            user_id = user.get_uid()
        else:
            to_email = mailaddr
    else:
        if user.load_username(owner):
            to_email = user.email
            user_id = user.get_uid()
        else:
            to_email = mailaddr

    company = addressbook.get_company() or external
    now_str = datetime.datetime.now().strftime(settings.email_date_format())
    subject = f"fax: {company} {now_str}"
    text = f"{LANG['TO']}: {company}"

    desc = addressbook.get_description()
    if desc:
        text += f" ({desc})"
    if regarding:
        text += f"\nRe: {regarding}\n"

    # Fatal branch
    if fatal:
        why_label = LANG["FAX_WHY"].get(why, why)
        subject = f"{why_label} {subject}"
        text = f"{LANG['FAX_FAILED']}: {why_label} {status}\n\n{text}"

        now_tag = datetime.datetime.now().strftime("%Y-%m-%d")
        time_tag = datetime.datetime.now().strftime("%H%M%S")
        faxpath = os.path.join(TMPDIR, f"{now_tag}-{external}-{time_tag}-{jobid}")
        mkdirs(faxpath)

        if convert2pdf(faxpath, faxfiles):
            print(f"Emailing pdf file to {to_email}")
            pdf_file = os.path.join(faxpath, "fax.pdf")
            send_mail(to_email, from_email, subject, text, file=pdf_file, altname=f"{external}.pdf")
            if os.path.exists(pdf_file):
                try:
                    os.remove(pdf_file)
                    os.rmdir(faxpath)
                except OSError:
                    pass
        else:
            avantfaxlog("notify> FAILED to create PDF for failed fax", echo=False)
            send_mail(to_email, from_email, subject, f"{text}\nFAILED to create PDF for failed fax")
        return 0

    # Alert / retry branch
    if alert:
        why_label = LANG["FAX_WHY"].get(why, why)
        subject = f"Fax {groupid} {LANG['TO']} {external} {why_label}"
        text = f"{why_label} {status}\n\n{text}"
        if next_try:
            text += f"\nFAX --> {next_try}"
        send_mail(to_email, from_email, subject, text)
        return 0

    # Success / faxdone branch
    if not faxdone:
        return 0

    now = datetime.datetime.now()
    faxpath = os.path.join(
        ARCHIVE_SENT,
        now.strftime("%Y"),
        now.strftime("%m"),
        now.strftime("%d"),
        external,
        now.strftime("%H%M%S"),
        str(jobid),
    )
    mkdirs(faxpath)

    if convert2pdf(faxpath, faxfiles):
        pdf_file = os.path.join(faxpath, "fax.pdf")
        thumbnail = os.path.join(faxpath, "thumb.png")

        pdf_preview(faxpath)

        outbox = ArchiveOut(db=session)
        pages_int = int(totpages) if totpages.isdecimal() else 0
        if outbox.create(faxpath, user_id, cid, external, pages_int):
            text += f"\nFax ID: {outbox.get_fid()}\n{LANG['PN_PAGES']}: {totpages}\n"
            if regarding:
                clean_regarding = decode_entity(regarding)
                outbox.set_note(clean_regarding, None, user_id)
        else:
            avantfaxlog(f"notify> FAILED to add Sent fax '{faxpath}' to ArchiveOut", echo=False)

        if NOTIFY_ON_SUCCESS:
            att_file = pdf_file if NOTIFY_INCLUDE_PDF else None
            alt_name = f"{external}.pdf" if NOTIFY_INCLUDE_PDF else None
            embed_img = None if NOTIFY_INCLUDE_PDF else thumbnail
            send_mail(to_email, from_email, subject, f"Fax: OK\n\n{text}", file=att_file, altname=alt_name, embedd=embed_img)
            avantfaxlog(f"notify> Notification email sent to {to_email}", echo=False)
        else:
            avantfaxlog(f"notify> Skipping notification email to {to_email} as per config setting NOTIFY_ON_SUCCESS", echo=False)
    else:
        avantfaxlog("notify> FAILED to create PDF for Archive", echo=False)
        send_mail(to_email, from_email, subject, f"Fax: OK\nFailed to create PDF for Archive:-(\n\n{text}")

    print("Done")
    return 0


def main() -> None:
    code = run_notify()
    sys.exit(code)


if __name__ == "__main__":
    main()
