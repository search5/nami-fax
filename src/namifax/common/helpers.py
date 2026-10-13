from __future__ import annotations

import html
import logging
import os
import re
import secrets
import shlex
import shutil
import string
import subprocess
import syslog
import tempfile
import unicodedata
from typing import Any, Dict, List, Optional, Sequence

from PIL import Image

from namifax.common.settings import binary as settings_binary
from namifax.common.settings import papersize as settings_papersize


DEFAULT_ADMIN_EMAIL = "admin@localhost"

MIME_TYPES = {
    "pdf": "application/pdf",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "txt": "text/plain",
    "ps": "application/postscript",
    "eps": "application/postscript",
    "html": "text/html",
    "htm": "text/html",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

UPLOAD_ERRORS = {
    1: "The uploaded file exceeds the upload_max_filesize directive in php.ini",
    2: "The uploaded file exceeds the MAX_FILE_SIZE directive that was specified in the HTML form",
    3: "The uploaded file was only partially uploaded",
    4: "No file was uploaded",
    6: "Missing a temporary folder",
    7: "Failed to write file to disk",
    8: "File upload stopped by extension",
}


def clean_faxnum(fnum: Optional[str]) -> str:
    """Strip all non-numeric and non-plus characters from fax number."""
    if not fnum:
        return ""
    return re.sub(r"[^\d+]", "", str(fnum))


def genpasswd(length: int = 8) -> str:
    """Generate cryptographically secure random alphanumeric password."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def rem_nl(text: str) -> str:
    """Remove newline and carriage return characters from text."""
    if not text:
        return ""
    return str(text).replace("\r\n", "").replace("\n", "").replace("\r", "")


def str_len(text: str) -> int:
    """Return length of string."""
    return len(text) if text else 0


def unaccent(text: str) -> str:
    """De-accent Unicode characters into their ASCII base equivalents."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return nfkd.encode("ASCII", "ignore").decode("utf-8")


def strip_sipinfo(text: str) -> str:
    """Strip SIP host/domain information from CallerID (regex: ^(.*)@(.*)$)."""
    if not text:
        return ""
    match = re.match(r"^(.*)@(.*)$", str(text))
    return match.group(1) if match else str(text)


def split_emails(emails: str) -> List[str]:
    """Split comma, semicolon, or whitespace separated email string into list."""
    if not emails:
        return []
    parts = re.split(r"[,;\s]+", str(emails).strip())
    return [p for p in parts if p]


def invalid_email(email: str) -> bool:
    """Validate email address. Returns True if invalid, False if valid."""
    if not email:
        return True
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    return not bool(re.match(pattern, str(email).strip()))


def process_template(template: str, match: str, values: Sequence[Any]) -> str:
    """Sequentially substitute match tokens in template with values."""
    res = template
    for val in values:
        res = res.replace(match, str(val), 1)
    return res


def process_html_template(template: str, match: str, values: Sequence[Any]) -> str:
    """Sequentially substitute match tokens in template with HTML-escaped values."""
    res = template
    for val in values:
        res = res.replace(match, html.escape(str(val)), 1)
    return res


def mime_by_suffix(filename: str) -> str:
    """Return MIME type corresponding to file extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return MIME_TYPES.get(ext, "application/octet-stream")


def get_filetype(filename: str) -> str:
    """Identify file type by suffix or basic content."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext or "unknown"


def tmpfilename(suffix: str = "") -> str:
    """Generate unique temporary file path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


def hylafax_date_to_iso(value: Any) -> str:
    """HylaFAX dates (``2026:10:01 10:05:09``, or the slash form used in archive paths) as ISO ``YYYY-MM-DD HH:MM:SS``.

    An unreadable value becomes the current time rather than an unsortable string in the archive.
    """
    import datetime as _dt

    match = re.match(r"^\s*(\d{4})[:/-](\d{2})[:/-](\d{2})(?:[ T](\d{2}):(\d{2}):(\d{2}))?", str(value or ""))
    if match:
        year, month, day, hour, minute, second = (int(g) if g else 0 for g in match.groups())
        try:
            return _dt.datetime(year, month, day, hour, minute, second).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def mkdirs(path: str, mode: int = 0o777) -> bool:
    """Recursively create directories."""
    try:
        os.makedirs(path, mode=mode, exist_ok=True)
        return True
    except OSError:
        return False


def fupload_error_code(code: int) -> str:
    """Return human readable upload error description."""
    return UPLOAD_ERRORS.get(code, "Unknown upload error")


def avantfaxlog(text: str, echo: bool = False, session: Any = None) -> None:
    """Record an event in the SysLog table (as the legacy avantfaxlog does) and in the OS syslog.

    Web code passes the request session. Hook processes pass nothing, so the entry is written
    through a short-lived session on the configured database. Logging never raises: a database
    problem must not break the caller.
    """
    msg = f"AvantFAX: {text}"
    if echo:
        print(msg)
    try:
        syslog.openlog("AvantFAX", syslog.LOG_PID, syslog.LOG_LOCAL0)
        syslog.syslog(syslog.LOG_INFO, text)
        syslog.closelog()
    except Exception:
        pass
    try:
        from namifax.db.provider import active_session
        from namifax.services.syslog import SysLogService

        session = session if session is not None else active_session()
        if session is not None:
            SysLogService(session).add(text)
        else:
            from namifax.db.provider import cli_session

            with cli_session() as own_session:
                SysLogService(own_session).add(text)
    except Exception:
        pass


def get_admin_email() -> str:
    """Return configured administrator email."""
    return os.environ.get("ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL)


def phone_lookup(number: str, db: Any = None) -> Optional[Dict[str, Any]]:
    """Look up address book company and contact details by phone/fax number."""
    if not number:
        return None
    cleaned = clean_faxnum(number)
    if not cleaned:
        return None

    from namifax.services.addressbook import NFAddressBook

    ab = NFAddressBook(db=db)
    res = ab.addressbookfax.find({"faxnumber": cleaned}, reduce_single=False)
    if not res:
        return None

    row = res[0]
    cid = row.get("abook_id")
    if cid:
        ab.loadbycid(cid)
        row["company"] = ab.company
    return row


def get_company_details(
    abookfax_id: Optional[int] = None,
    orig_faxnum: Optional[str] = None,
    companyid: Optional[int] = None,
    db: Any = None,
) -> Dict[str, Any]:
    """Retrieve combined company and fax information."""
    from namifax.services.addressbook import NFAddressBook

    ab = NFAddressBook(db=db)
    details: Dict[str, Any] = {
        "company": None,
        "faxnumber": orig_faxnum,
        "abook_id": companyid,
        "abookfax_id": abookfax_id,
    }

    if abookfax_id and ab.loadbyfaxnumid(abookfax_id):
        details["company"] = ab.company
        details["abook_id"] = ab.abook_id
        details["faxnumber"] = ab.fax_array.get("faxnumber", orig_faxnum)
        return details

    if companyid and ab.loadbycid(companyid):
        details["company"] = ab.company
        details["abook_id"] = companyid
        return details

    if orig_faxnum:
        found = phone_lookup(orig_faxnum, db=db)
        if found:
            details["company"] = found.get("company")
            details["abook_id"] = found.get("abook_id")
            details["abookfax_id"] = found.get("abookfax_id")
            details["faxnumber"] = found.get("faxnumber", orig_faxnum)

    return details


def list_languages(languages_dir: str = "") -> List[Dict[str, str]]:
    """List available language translation codes."""
    langs = [
        {"code": "en", "name": "English"},
        {"code": "es", "name": "Spanish"},
        {"code": "fr", "name": "French"},
        {"code": "de", "name": "German"},
        {"code": "it", "name": "Italian"},
        {"code": "nl", "name": "Dutch"},
        {"code": "pt", "name": "Portuguese"},
        {"code": "tr", "name": "Turkish"},
    ]
    return langs


def decode_entity(text: str) -> str:
    """Decode HTML/XML entities."""
    return html.unescape(text) if text else ""


def _active_mailer(session: Any = None) -> Any:
    """MailerService configured with the SMTP gateway saved in the database (spec 39, section 3.2).

    Web code passes the request session. Command-line hooks pass nothing, so the settings are read
    through a short-lived session on the configured database. Any problem reading them falls back
    to the local MTA, so a mail is still attempted (never silently kept in memory).
    """
    from namifax.db.provider import active_session
    from namifax.services.mailer import MailerService

    session = session if session is not None else active_session()
    if session is not None:
        return MailerService.get_active_mailer(session)
    try:
        from namifax.db.provider import cli_session

        with cli_session() as own_session:
            return MailerService.get_active_mailer(own_session)
    except Exception:
        return MailerService.local_mta()


def send_mail(
    to: str | Sequence[str],
    from_addr: Optional[str],
    subject: str,
    text: str,
    file: Optional[str] = None,
    altname: Optional[str] = None,
    embedd: Optional[str] = None,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    session: Any = None,
) -> bool:
    """Send email through the SMTP gateway saved in the database.

    ``from_addr`` is the sender of this message; without it the gateway's configured address is used.
    """
    mailer = _active_mailer(session)
    if from_addr:
        mailer.admin_email = from_addr
    mailer.set_message(text, subject=subject)
    if file and os.path.exists(file):
        mailer.attach_file(file, alt_name=altname)
    if embedd and os.path.exists(embedd):
        mailer.embed_image(embedd)
    if cc:
        mailer.set_cc(cc)
    if bcc:
        mailer.set_bcc(bcc)

    recipients = split_emails(to) if isinstance(to, str) else list(to)
    if mailer.sendmail(recipients):
        return True
    avantfaxlog(f"send_mail> MAIL ERROR: {mailer.get_error()}", session=session)
    return False


def convert2pdf(path: str, convertfiles: Sequence[str]) -> bool:
    """Turn the files of a fax into one ``fax.pdf`` in ``path`` (the original's convert2pdf).

    TIFFs become pages directly, PostScript goes through Ghostscript, PDFs are taken as they are; the cover page (a name with
    "cover") is first, then the other PDFs, the PostScript and the TIFFs. A file that cannot be converted fails the whole call
    (and no half-made PDF is left) instead of being left out. Files that do not exist are skipped.
    """
    from pypdf import PdfReader, PdfWriter

    os.makedirs(path, exist_ok=True)
    pdffile = os.path.join(path, "fax.pdf")
    tiffs, postscripts, covers, pdfs = [], [], [], []
    for name in convertfiles:
        if not os.path.exists(name):
            continue
        lower = name.lower()
        if re.search(r"\.tiff?$", lower):
            tiffs.append(name)
        elif re.search(r"\.ps$", lower):
            postscripts.append(name)
        elif "cover" in os.path.basename(lower):
            covers.append(name)
        else:
            pdfs.append(name)
    if not (tiffs or postscripts or covers or pdfs):
        return False

    writer = PdfWriter()
    temporary: List[str] = []
    try:
        for name in [*covers, *pdfs]:
            for page in PdfReader(name).pages:
                writer.add_page(page)
        if postscripts:
            gs = settings_binary("gs")
            if not gs:
                return False
            out = tmpfilename(".pdf")
            temporary.append(out)
            argv = [gs, "-dCompatibilityLevel=1.4", "-dSAFER", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=pdfwrite",
                    f"-sOutputFile={out}", f"-sPAPERSIZE={settings_papersize()}", "-f", *postscripts]
            if subprocess.run(argv, capture_output=True, check=False).returncode != 0:
                return False
            for page in PdfReader(out).pages:
                writer.add_page(page)
        for name in tiffs:                                       # (the original: tiff2ps | gs, one PDF for each TIFF)
            out = tmpfilename(".pdf")
            temporary.append(out)
            if not tiff2pdf(name, out):
                return False
            for page in PdfReader(out).pages:
                writer.add_page(page)
        with open(pdffile, "wb") as out_file:
            writer.write(out_file)
        return True
    except Exception:
        if os.path.exists(pdffile):
            os.remove(pdffile)
        return False
    finally:
        for name in temporary:
            if os.path.exists(name):
                os.remove(name)


def copy_tiff(src: str, dst: str, group4: bool = False) -> bool:
    """Copy a received fax TIFF into the archive (the original's tiffcp); ``group4`` stores it recompressed as CCITT Group 4."""
    try:
        if not group4:
            shutil.copy2(src, dst)
            return True
        with Image.open(src) as img:
            frames = []
            for i in range(getattr(img, "n_frames", 1)):
                img.seek(i)
                frames.append(img.convert("1"))
        frames[0].save(dst, save_all=True, append_images=frames[1:], format="TIFF", compression="group4")
        return True
    except (OSError, ValueError):
        return False


def annotated_pages(tiff_file: str, text: str, gravity: str = "southeast") -> List[Image.Image]:
    """Every page of the TIFF with ``text`` written at ``gravity`` (north/south, optionally east/west; centred otherwise)."""
    from PIL import ImageDraw, ImageFont

    pages: List[Image.Image] = []
    with Image.open(tiff_file) as img:
        for i in range(getattr(img, "n_frames", 1)):
            img.seek(i)
            page = img.convert("L")
            try:
                font = ImageFont.load_default(size=25)
            except TypeError:
                font = ImageFont.load_default()
            draw = ImageDraw.Draw(page)
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            width, height = right - left, bottom - top
            margin = 10
            x = page.width - width - margin if "east" in gravity else margin if "west" in gravity else (page.width - width) // 2
            y = margin if gravity.startswith("north") else page.height - height - margin * 2 if gravity.startswith("south") \
                else (page.height - height) // 2
            draw.text((x, y), text, fill=0, font=font)
            pages.append(page)
    return pages


def annotate_fax(tiff_file: str, text: str, pdf_out: str, gravity: str = "southeast") -> bool:
    """Write a PDF of the fax with ``text`` (for example "FaxID: 42") stamped on every page (the original's annotate_fax)."""
    try:
        pages = annotated_pages(tiff_file, text, gravity)
        if not pages:
            return False
        pages[0].convert("RGB").save(pdf_out, save_all=True, append_images=[p.convert("RGB") for p in pages[1:]],
                                     format="PDF", resolution=200)
        return True
    except (OSError, ValueError):
        return False


def pdf_preview(path: str) -> bool:
    """Create thumbnail image of fax.pdf or fax.tif located in path."""
    if not path or not os.path.exists(path):
        return False

    thumbfile = os.path.join(path, "thumb.png")
    tiffile = os.path.join(path, "fax.tif")
    pdffile = os.path.join(path, "fax.pdf")

    if os.path.exists(tiffile):
        return static_preview(path, pages=1)

    if not os.path.exists(pdffile):
        return False

    from namifax.services.fax_images import render_pdf_previews

    if render_pdf_previews(path):                       # a real picture of the pages
        return True

    if not os.path.exists(thumbfile):
        try:
            img = Image.new("RGB", (120, 160), color=(240, 240, 240))
            img.save(thumbfile, format="PNG")
        except Exception:
            return False
    return True


def tiff2pdf(tiff_file: str, pdf: str) -> bool:
    """Convert TIFF file to PDF matching legacy tiff2pdf semantics."""
    if not os.path.exists(tiff_file):
        return False

    dir_name = os.path.dirname(pdf)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    # 1. Try native LibTIFF tiff2pdf binary if available in PATH
    try:
        import subprocess

        proc = subprocess.run(
            ["tiff2pdf", "-o", pdf, tiff_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        if proc.returncode == 0 and os.path.exists(pdf) and os.path.getsize(pdf) > 0:
            return True
    except Exception:
        pass

    # 2. Pillow fallback: the pages stay black and white, and the PDF page is as many inches as the fax is (a fax has its own
    #    resolution, 204 x 196 dpi "fine" or 204 x 98 dpi "normal"; the pixels are made square as ``tiff2ps`` does)
    try:
        with Image.open(tiff_file) as img:
            pages: List[Image.Image] = []
            dpi = 0.0
            for i in range(getattr(img, "n_frames", 1)):
                img.seek(i)
                xres, yres = (float(v) for v in (img.info.get("dpi") or (0, 0)))
                if min(xres, yres) < 50:                       # none given (Pillow then says 1 x 1): a fax is 204 x 196 dpi
                    xres, yres = 204.0, 196.0
                dpi = dpi or xres
                page = img.copy() if img.mode in ("1", "L", "RGB") else img.convert("RGB")
                if abs(xres - yres) > 0.1 * xres:
                    page = page.resize((page.width, max(round(page.height * xres / yres), 1)), Image.NEAREST)
                pages.append(page)
            if pages:
                pages[0].save(pdf, save_all=True, append_images=pages[1:], format="PDF", resolution=dpi)
                return True
    except Exception:
        pass

    return False


def static_preview(path: str, pages: int = 1) -> bool:
    """Make the page images (``page<N>.png``) and the thumbnail of a received fax, as the original's static_preview does."""
    from namifax.services.fax_images import render_previews

    if not path or not os.path.exists(path):
        return False
    try:
        return render_previews(path) > 0
    except Exception:
        return False


def faxinfo(path: str) -> Optional[Dict[str, Any]]:
    """What is known about a received fax (the original's faxinfo()): ``Sender``, ``Pages``, ``Received`` and the caller ids.

    HylaFAX's own ``faxinfo -n`` is asked when it is installed, else the TIFF is read directly. An unknown sender becomes the
    reserved number, a SIP suffix is cut from the caller id, and a file that is not a fax (or lacks a sender, page count or date)
    answers None so that the caller can report it as corrupted.
    """
    from namifax.services.addressbook import RESERVED_FAX_NUM

    if not os.path.exists(path):
        return None

    values: Dict[str, Any] = {}
    binary = settings_binary("faxinfo")
    if binary:
        try:
            proc = subprocess.run([binary, "-n", path], capture_output=True, text=True, timeout=10, check=False)
            for line in (proc.stdout or "").splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    values[key.strip()] = value.strip()
        except (OSError, subprocess.SubprocessError):
            values = {}
    if not values:
        values = _read_tiff(path)
    if not values:
        return None

    if re.search(r"unknown|unspecified", values.get("Sender", ""), re.I) or not values.get("Sender"):
        values["Sender"] = RESERVED_FAX_NUM
    if values.get("CallID1") and "@" in values["CallID1"]:
        values["CallID1"] = values["CallID1"].split("@", 1)[0]          # strip the SIP host
    return values if values.get("Sender") and values.get("Pages") and values.get("Received") else None


def _read_tiff(path: str) -> Dict[str, Any]:
    """The fax facts a TIFF carries itself: its pages, its date and (page name tag) the sending station; {} if it is no TIFF."""
    import datetime

    try:
        with Image.open(path) as img:
            if img.format != "TIFF":
                return {}
            tags = getattr(img, "tag_v2", {})
            stamp = tags.get(306)                                        # DateTime, "YYYY:MM:DD HH:MM:SS"
            if not (isinstance(stamp, str) and re.fullmatch(r"\d{4}:\d\d:\d\d \d\d:\d\d:\d\d", stamp.strip())):
                stamp = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y:%m:%d %H:%M:%S")
            return {"Sender": str(tags.get(285) or "").strip(), "Pages": str(getattr(img, "n_frames", 1)), "Received": stamp.strip()}
    except Exception:
        return {}


def bardecode(filename: str) -> Optional[str]:
    """The barcode of a fax (the original's bardecode()): only when ENABLE_BARDECODE_SUPPORT is on, through BARDECODE_COMMAND
    (``%s`` is the file; no shell is involved), else through zbar when that is installed."""
    from namifax.common import settings as cfg

    if not cfg.bardecode_enabled() or not filename or not os.path.exists(filename):
        return None

    binary = cfg.bardecode_binary()
    if os.path.exists(binary):
        try:
            argv = [filename if part == "%s" else part for part in shlex.split(cfg.bardecode_command())]
            argv = [a.replace("%s", filename) for a in argv]
            proc = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=60)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        return None

    zbar = cfg.binary("zbarimg")
    if zbar:
        try:
            proc = subprocess.run([zbar, "--raw", "-q", filename], capture_output=True, text=True, check=False, timeout=60)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def ocr_faxcontent(filename: str) -> Optional[str]:
    """The text of a fax (the original's ocr_faxcontent()): only when ENABLE_OCR_SUPPORT is on, through OCR_COMMAND
    (input file, output base name, language) when OCR_BINARY exists, else through Tesseract's Python binding."""
    from namifax.common import settings as cfg

    if not cfg.ocr_enabled() or not filename or not os.path.exists(filename):
        return None

    language = cfg.ocr_language()
    if os.path.exists(cfg.ocr_binary()):
        with tempfile.TemporaryDirectory() as work:
            base = os.path.join(work, "ocr")
            try:
                template = shlex.split(cfg.ocr_command())
                values = iter([filename, base, language])
                argv = []
                for part in template:
                    while "%s" in part:
                        part = part.replace("%s", next(values, ""), 1)
                    argv.append(part)
                subprocess.run(argv, capture_output=True, check=False, timeout=600)
                with open(base + ".txt", "r", encoding="utf-8", errors="replace") as handle:
                    return handle.read().strip() or None
            except (OSError, subprocess.SubprocessError, ValueError) as e:
                logging.getLogger("namifax").error("OCR command failed for %s: %s", filename, e)
                return None

    try:
        from namifax.services.ocr import OcrService

        ocr = OcrService(lang=language)
        res = ocr.extract_text_from_tiff(filename)
        if res.get("success") and res.get("text"):
            return str(res["text"]).strip()
        txt = ocr.extract_text_from_image(filename)
        return txt.strip() if txt else None
    except Exception:
        logging.getLogger("namifax").exception("OCR failed for %s", filename)
        return None


