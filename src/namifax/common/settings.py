"""Settings under the names of the original's local_config.php, read from the environment with the original's defaults."""

from __future__ import annotations

import os
import shutil
from typing import Optional

TRUE = ("1", "true", "True", "yes")


def flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    return default if raw is None else raw in TRUE


def text(name: str, default: str) -> str:
    return os.environ.get(name) or default


def number(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    return int(raw) if raw.isdecimal() else default


def restricted_user_mode() -> bool:
    """``RESTRICTED_USER_MODE``: an archive search needs the user's line (or DID route) AND category, not either one."""
    return flag("RESTRICTED_USER_MODE", False)


def inbox_list_modem() -> bool:
    """``INBOX_LIST_MODEM``: list the inbox line by line (modem order, newest first inside a line) instead of by date."""
    return flag("INBOX_LIST_MODEM", False)


def show_all_contacts() -> bool:
    """``SHOW_ALL_CONTACTS`` (on by default): off, a contact lookup needs a search of at least two characters."""
    return flag("SHOW_ALL_CONTACTS", True)


def contact_lookup_allowed(query: str) -> bool:
    return show_all_contacts() or len(query or "") > 1


def sendfax_use_coverpage() -> bool:
    """``SENDFAX_USE_COVERPAGE`` (on by default): the Send Fax form starts with the cover page switched on."""
    return flag("SENDFAX_USE_COVERPAGE", True)


def sendfax_requeue_email() -> bool:
    """``SENDFAX_REQUEUE_EMAIL`` (on by default): the Send Fax form starts with "notify on retry" ticked."""
    return flag("SENDFAX_REQUEUE_EMAIL", True)


def max_username_size() -> int:
    """``MAX_USERNAME_SIZE`` (15): the length limit of the user name field."""
    return number("MAX_USERNAME_SIZE", 15)


def max_passwd_size() -> int:
    """``MAX_PASSWD_SIZE`` (15): the longest password that can be set."""
    return number("MAX_PASSWD_SIZE", 15)


def min_passwd_size() -> int:
    """``MIN_PASSWD_SIZE`` (8): the shortest password that can be set."""
    return number("MIN_PASSWD_SIZE", 8)


def max_email_size() -> int:
    """``MAX_EMAIL_SIZE`` (99): the length limit of the e-mail address field."""
    return number("MAX_EMAIL_SIZE", 99)


def default_faxes_per_page_inbox() -> int:
    """``DEFAULT_FAXES_PER_PAGE_INBOX`` (25): the Inbox page size of a user who has not chosen one."""
    return number("DEFAULT_FAXES_PER_PAGE_INBOX", 25)


def default_faxes_per_page_archive() -> int:
    """``DEFAULT_FAXES_PER_PAGE_ARCHIVE`` (30): the Archive page size of a user who has not chosen one."""
    return number("DEFAULT_FAXES_PER_PAGE_ARCHIVE", 30)


def focus_on_new_fax() -> bool:
    """``FOCUS_ON_NEW_FAX`` (off by default): the inbox check brings the window forward when a new fax arrives."""
    return flag("FOCUS_ON_NEW_FAX", False)


def focus_on_new_fax_popup() -> bool:
    """``FOCUS_ON_NEW_FAX_POPUP`` (off by default): a new fax is announced (and the user's sound played) in the browser."""
    return flag("FOCUS_ON_NEW_FAX_POPUP", False)


def whitepages_url() -> str:
    """``WHITEPAGES``: the address of a reverse phone look-up; the number is put behind its last ``=``."""
    return text("WHITEPAGES", "http://www.whitepages.com/search/ReversePhone?full_phone=")


def hylaspool() -> str:
    return text("HYLASPOOL", "/var/spool/hylafax").rstrip("/") or "/"


def archive_dir() -> str:
    return text("AVANTFAX_ARCHIVE", f"{hylaspool()}/archive")


def sent_dir() -> str:
    return text("ARCHIVE_SENT", f"{hylaspool()}/sent")


def phonebook_path() -> str:
    return text("PHONEBOOK", f"{hylaspool()}/etc/phonebook")


def binary(name: str) -> Optional[str]:
    """Where a program is: the variable named like it (``GS``, ``FAXINFO``...), then BINARYDIR, then the PATH."""
    named = os.environ.get(name.upper().replace("-", "_"))
    if named and os.path.exists(named):
        return named
    folder = os.environ.get("BINARYDIR")
    if folder:
        candidate = os.path.join(folder, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return shutil.which(name)


def email_date_format() -> str:
    return text("EMAIL_DATE_FORMAT", "%d.%m.%Y %H:%M")


def faxcover_date_format() -> str:
    return text("FAXCOVER_DATE_FORMAT", "%d.%m.%Y %H:%M")


def papersize() -> str:
    return text("PAPERSIZE", "a4")


def dpi() -> int:
    return number("DPI", 200)


def callid_index(kind: str) -> int:
    """Which CallID line of the fax holds the caller number (``CIDNumber``), the caller name (``CIDName``) or the dialled number
    (``DIDNum``): the original's $CALLIDn_CIDNumber / _CIDName / _DIDNum, here CALLIDN_CIDNUMBER and so on."""
    defaults = {"CIDNumber": 1, "CIDName": 2, "DIDNum": 3}
    return number(f"CALLIDN_{kind.upper()}", defaults[kind])


def hylafax_bin() -> str:
    return f"{hylaspool()}/bin"


def bardecode_enabled() -> bool:
    return flag("ENABLE_BARDECODE_SUPPORT", False)


def bardecode_binary() -> str:
    return text("BARDECODE_BINARY", f"{hylafax_bin()}/bardecode")


def bardecode_command() -> str:
    return text("BARDECODE_COMMAND", f"{bardecode_binary()} -t any -f %s")


def ocr_enabled() -> bool:
    return flag("ENABLE_OCR_SUPPORT", False)


def ocr_binary() -> str:
    return text("OCR_BINARY", "/usr/local/bin/tesseract")


def ocr_command() -> str:
    return text("OCR_COMMAND", f"{ocr_binary()} %s %s -l %s")


def ocr_language() -> str:
    return text("OCR_LANGUAGE", "eng")


_ENCODINGS = {"base64encoding": "base64", "base64": "base64", "quotedprintableencoding": "quoted-printable",
              "quoted-printable": "quoted-printable", "8bit": "8bit", "8bitencoding": "8bit", "7bit": "7bit", "7bitencoding": "7bit"}


def email_encoding(part: str) -> str:
    """The transfer encoding of the text or HTML part (``EMAIL_ENCODING_TEXT`` / ``_HTML``); Base64 like the original."""
    return _ENCODINGS.get(text(f"EMAIL_ENCODING_{part.upper()}", "Base64Encoding").lower(), "base64")


def email_charset() -> str:
    return text("EMAIL_ENCODING_CHARSET", "UTF-8").lower()
