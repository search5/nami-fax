#!/usr/bin/env python3
"""AvantFAX modern CLI replacement for includes/faxcover.php.

Generates HylaFAX fax cover pages by parsing command line options, resolving
user account details, and substituting placeholders into EPS/PS/HTML templates.
"""

from __future__ import annotations

import datetime
import getopt
import os
import re
import sys
import textwrap
from typing import Any, Dict, List, Sequence

# Ensure src directory is on sys.path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from namifax.common import settings
from namifax.common.helpers import (
    avantfaxlog,
    decode_entity,
    invalid_email,
    rem_nl,
)
from sqlalchemy import select

from namifax.db.provider import cli_session
from namifax.models.useraccount import UserAccount

USAGE = (
    "Usage: faxcover [-t to] [-c comments] [-p #pages] [-l to-location] [-m maxcomments] [-z maxlencomments] "
    "[-r regarding] [-v to-voice-number] [-x to-company] [-C template-file] [-D date-format] [-L from-location] "
    "[-M from-mail-address] [-N from-fax-number] [-V from-voice-number] [-X from-company] [-s pagesize] "
    "-f from -n fax-number\n"
)

INSTALLDIR = os.environ.get("AVANTFAX_INSTALLDIR", "/var/www/avantfax")
COVERPAGE_FILE = os.environ.get("COVERPAGE_FILE", "cover.ps")
COVERPAGE_MATCH = os.environ.get("COVERPAGE_MATCH", "XXXX-")
CPAGE_LINELEN = int(os.environ.get("CPAGE_LINELEN", "80"))
FAXCOVER_DATE_FORMAT = settings.faxcover_date_format()
FROM_COMPANY = os.environ.get("FROM_COMPANY", "")
FROM_LOCATION = os.environ.get("FROM_LOCATION", "")
FROM_VOICENUMBER = os.environ.get("FROM_VOICENUMBER", "")
FROM_FAXNUMBER = os.environ.get("FROM_FAXNUMBER", "")
USE_HTML_COVERPAGE = os.environ.get("USE_HTML_COVERPAGE", "0") in ("1", "true", "True")
NUM_PAGES_FOLLOW = os.environ.get("NUM_PAGES_FOLLOW", "0") in ("1", "true", "True")
HTML2PS = settings.binary("html2ps") or "html2ps"


def ps_text(value: Any) -> str:
    """Text made safe inside a PostScript string: ``\\``, ``(`` and ``)`` escaped, newlines dropped, accented letters as the
    octal codes of the Mac Roman encoding the original's unaccent() used, anything the font cannot show as ``?``."""
    text = decode_entity(str(value)) if value is not None else ""
    out = []
    for ch in text.replace("\r", "").replace("\n", " "):
        if ch in "\\()":
            out.append("\\" + ch)
        elif ord(ch) < 128:
            out.append(ch)
        else:
            try:
                out.append("\\%03o" % ch.encode("mac_roman")[0])
            except UnicodeEncodeError:
                out.append("?")
    return "".join(out)


def process_template(template_path: str, match: str, values: Dict[str, Any], *, html: bool = False,
                     raw: Sequence[str] = ()) -> List[str]:
    """Substitute every ``XXXX-symbol`` of the template with its value (exact symbol names; unknown ones become empty)."""
    import html as htmllib

    if not os.path.exists(template_path):
        return []
    symbol = re.compile(re.escape(match) + r"([A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*)")
    convert = (lambda v: htmllib.escape(str(v))) if html else ps_text

    def swap(found: "re.Match[str]") -> str:
        value = values.get(found.group(1))
        if value is None:
            return ""
        return str(value) if found.group(1) in raw else convert(value)

    with open(template_path, "r", encoding="utf-8", errors="replace") as handle:
        return [symbol.sub(swap, line) for line in handle]


def _first_row(db: Any, columns: list, **where: Any) -> Dict[str, Any] | None:
    """The first UserAccount row matching ``where``, as a dict, or None."""
    row = db.execute(select(*columns).filter_by(**where).limit(1)).first()
    return dict(row._mapping) if row else None


def _resolve_sender(db: Any, from_name: str, from_email: str | None) -> tuple[str, str | None]:
    """Resolve sender display name / email from UserAccount (legacy faxcover.php lookup)."""
    name, email, username = UserAccount.name, UserAccount.email, UserAccount.username
    if from_email:
        row = _first_row(db, [name], email=from_email)
        if row:
            return row.get("name", from_name), from_email
        if not invalid_email(from_name):
            row2 = _first_row(db, [name], email=from_name)
            if row2:
                return row2.get("name", from_name), from_name
        return from_name, from_email

    row = _first_row(db, [email], name=from_name)
    if row:
        return from_name, row.get("email", from_email)
    row_u = _first_row(db, [name, email], username=from_name)
    if row_u:
        return row_u.get("name", from_name), row_u.get("email", from_email)
    return from_name, from_email


def run_faxcover(argv: Sequence[str] | None = None, *, db: Any = None) -> int:
    """Execute faxcover page generator."""
    args = list(argv[1:]) if argv is not None else list(sys.argv[1:])

    try:
        opts, _ = getopt.getopt(args, "t:c:p:l:m:z:r:v:x:C:D:L:N:V:X:s:f:n:M:")
    except getopt.GetoptError:
        print(USAGE, end="")
        return 0

    opt_dict: Dict[str, str] = dict(opts)

    if "-f" not in opt_dict or "-n" not in opt_dict:
        print(USAGE, end="")
        return 0

    from_name = opt_dict["-f"]
    from_email = opt_dict.get("-M")
    to_fax = opt_dict["-n"]

    avantfaxlog(f"faxcover> from: '{from_name}' email: '{from_email}'", echo=False)

    # Optional DB lookup for user details
    try:
        if db is not None:
            from_name, from_email = _resolve_sender(db, from_name, from_email)
        else:
            with cli_session(ensure_schema=True) as opened:
                from_name, from_email = _resolve_sender(opened, from_name, from_email)
    except Exception:
        pass

    # Template selection: a .ps file, or an .html file when HTML cover pages are allowed
    coverpage_file = os.path.join(INSTALLDIR, "images", COVERPAGE_FILE)
    using_html = False
    if "-C" in opt_dict:
        wanted = opt_dict["-C"]
        wanted = wanted if os.path.exists(wanted) else os.path.join(INSTALLDIR, "images", wanted)
        kind = os.path.splitext(wanted)[1].lower()
        if kind in (".html", ".htm"):
            if USE_HTML_COVERPAGE:
                coverpage_file, using_html = wanted, True
        elif kind == ".ps":
            coverpage_file = wanted
    elif os.path.splitext(coverpage_file)[1].lower() in (".html", ".htm") and USE_HTML_COVERPAGE:
        using_html = True

    date_fmt = opt_dict.get("-D", FAXCOVER_DATE_FORMAT)
    try:
        today_date = datetime.datetime.now().strftime(date_fmt)
    except Exception:
        today_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    values: Dict[str, Any] = {
        "from": from_name,
        "from-mail-address": from_email,
        "to": opt_dict.get("-t"),
        "to-company": opt_dict.get("-x"),
        "to-location": opt_dict.get("-l"),
        "to-voice-number": opt_dict.get("-v"),
        "to-fax-number": to_fax,
        "regarding": opt_dict.get("-r"),
        "from-company": opt_dict.get("-X", FROM_COMPANY),
        "from-location": opt_dict.get("-L", FROM_LOCATION),
        "from-voice-number": opt_dict.get("-V", FROM_VOICENUMBER),
        "from-fax-number": opt_dict.get("-N", FROM_FAXNUMBER),
        "page-count": opt_dict.get("-p"),
        "pageSize": opt_dict.get("-s"),
        "todays-date": today_date,
    }

    # Comments parsing
    fax_comments = opt_dict.get("-c", "")
    # Parse {key:val} syntax
    custom_tags = re.findall(r"{([^}]*)}", fax_comments)
    for tag in custom_tags:
        parts = tag.split(":", 1)
        if len(parts) == 2:
            values[parts[0].strip()] = parts[1].strip().strip("'")
    fax_comments = re.sub(r"{([^}]*)}", "", fax_comments)

    if NUM_PAGES_FOLLOW and str(values.get("page-count") or "").isdecimal():
        values["page-count"] = str(int(values["page-count"]) + 1)          # the cover page counts too

    if using_html:
        import html as htmllib
        import subprocess
        import tempfile

        values["comments"] = htmllib.escape(fax_comments).replace("\n", "<br />")
        page = "".join(process_template(coverpage_file, COVERPAGE_MATCH, values, html=True, raw=("comments",)))
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as handle:
            handle.write(page)
            name = handle.name
        try:
            result = subprocess.run([HTML2PS, name], capture_output=True, check=False)
        except OSError as err:
            sys.stderr.write(f"faxcover: cannot run {HTML2PS}: {err}\n")
            return 1
        finally:
            os.remove(name)
        sys.stdout.write(result.stdout.decode("utf-8", errors="replace"))
        return 0 if result.returncode == 0 else 1

    maxlen = int(opt_dict.get("-z", CPAGE_LINELEN))
    if fax_comments:
        for idx, line in enumerate(textwrap.wrap(fax_comments, width=maxlen)):
            values[f"comments{idx}"] = rem_nl(line)

    if os.path.exists(coverpage_file):
        sys.stdout.write("".join(process_template(coverpage_file, COVERPAGE_MATCH, values)))

    return 0


def main() -> None:
    code = run_faxcover()
    sys.exit(code)


if __name__ == "__main__":
    main()
