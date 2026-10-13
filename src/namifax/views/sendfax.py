"""NamiFAX SendFax View matching legacy NamiFAX behavior."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Any

from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from namifax.services.addressbook import RESERVED_FAX_NUM, NFAddressBook
from namifax.services.archive_in import ArchiveIn
from namifax.services.covers import Covers
from namifax.common import settings
from namifax.i18n import _
from namifax.services import upload_check
from namifax.services.modem import FaxModem
from namifax.services.sendfax_command import NothingToSend, Sender, SendRequest, build_plan
from namifax.services.user_account import NFUserAccount
from namifax.views.fax_rights import fax_access, load_fax


def _images_dir() -> str:
    return os.path.join(os.environ.get("AVANTFAX_INSTALLDIR", "/var/www/avantfax"), "images")


def _tmp_dir() -> str:
    return tempfile.gettempdir().rstrip("/") + "/"


def _faxcover_command() -> list[str]:
    configured = os.environ.get("NAMIFAX_FAXCOVER")
    return [configured] if configured else [sys.executable, "-m", "namifax.cli.faxcover"]


def _simulation_wanted() -> bool:
    """Only an explicit NAMIFAX_QUEUE_SIMULATION=1 (a development machine) may fake a send; otherwise a missing HylaFAX is an error."""
    return os.environ.get("NAMIFAX_QUEUE_SIMULATION", "").strip().lower() in ("1", "true", "yes")


def dispatch_sendfax(send: SendRequest, sender: Sender) -> dict[str, Any]:
    """Run sendfax (and faxcover for a cover page without a file) for the form, or simulate when HylaFAX is absent."""
    try:
        plan = build_plan(send, sender, images_dir=_images_dir(), tmp_dir=_tmp_dir(),
                          default_tsi=os.environ.get("DEFAULT_TSI_ID", ""))
    except NothingToSend:
        return {"success": False, "error": str(_("Select a file to send, or ask for a cover page."))}

    sendfax_bin = settings.binary("sendfax")
    if not sendfax_bin:
        if _simulation_wanted():
            return {"success": True, "jobid": str(uuid.uuid4().int)[:6], "destination": send.destinations.strip(),
                    "files_count": len(send.files), "simulated": True}
        return {"success": False, "error": str(_("The fax could not be sent: HylaFAX (the sendfax program) is not installed or not reachable on this server. "
                              "Ask the administrator.")), "simulated": False}

    binaries = {"sendfax": [sendfax_bin], "faxcover": _faxcover_command()}
    try:
        for path, content in plan.files_to_write.items():
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
        output = ""
        for step in plan.steps:
            argv = [*binaries[step.argv[0]], *step.argv[1:]]
            if step.stdout_to:
                with open(step.stdout_to, "wb") as sink:
                    result = subprocess.run(argv, stdout=sink, stderr=subprocess.PIPE, check=False)
                output = result.stderr.decode(errors="replace")
            else:
                result = subprocess.run(argv, capture_output=True, text=True, check=False)
                output = (result.stdout or "") + (result.stderr or "")
            if result.returncode != 0:
                return {"success": False, "error": output.strip() or f"{step.argv[0]} failed"}
        match = re.search(r"request id is (\d+)", output)
        return {"success": True, "output": output, "jobid": match.group(1) if match else None}
    except OSError as exc:
        return {"success": False, "error": f"{_('The fax could not be queued:')} {exc}"}
    finally:
        for path in [*plan.files_to_write, *plan.cleanup]:
            try:
                os.remove(path)
            except OSError:
                pass


def _sender_number(request, fax: ArchiveIn) -> str:
    """The number to answer: the address book's number for the fax, else the number it came from (blank if unusable)."""
    number = None
    book = NFAddressBook(db=request.dbsession)
    if fax.get_faxnumid() and book.loadbyfaxnumid(fax.get_faxnumid()):
        number = book.get_faxnumber()
    number = number or fax.get_origfaxnum() or ""
    return number if any(c.isdigit() for c in number) and number != RESERVED_FAX_NUM else ""


def _account(request) -> tuple[Sender, dict[str, Any]]:
    """The signed-in user as the sender of the fax, and their account values."""
    username = str((request.identity or {}).get("username") or "")
    account = NFUserAccount(db=request.dbsession)
    if not username or not account.load_username(username):
        return Sender(username=username), {}
    d = account.dbdata
    return Sender(name=d.get("name") or "", username=username, email=d.get("email") or "", company=d.get("from_company") or "",
                  location=d.get("from_location") or "", voicenumber=d.get("from_voicenumber") or "",
                  faxnumber=d.get("from_faxnumber") or ""), d


def _covers(request, account: dict[str, Any]) -> tuple[list[tuple[str, str]], str]:
    """(file, title) of every cover page, and the file of the user's own choice (the first one without)."""
    covers = Covers(db=request.dbsession)
    options, chosen = [], ""
    for file in covers.get_covers() or []:
        if covers.load_cover(file):
            options.append((file, covers.get_title() or file))
            if account.get("coverpage_id") and covers.get_cover_id() == account.get("coverpage_id"):
                chosen = file
    return options, chosen or (options[0][0] if options else "")


def _lines(request, account: dict[str, Any]) -> list[tuple[str, str]]:
    """The choices of the Line drop-down: 'any line' (empty value) only with the any_modem right, then the user's own lines
    (every configured one for a superuser)."""
    access = fax_access(request)
    modems = FaxModem(db=request.dbsession)
    devices = (modems.get_modems() if access.superuser else access.modems) or []
    choices = [("", str(_("Any Available Line (Auto)")))] if account.get("any_modem") else []
    for device in devices:
        if modems.load_device(device):
            choices.append((device, modems.get_alias() or device))
    return choices


def _send_request(params, files: list[str]) -> SendRequest:
    def text(name: str) -> str:
        return (params.get(name) or "").strip()

    return SendRequest(
        destinations=text("faxnumber") or text("destinations"), files=files, modem=text("modem") or None,
        to_person=text("to_person"), to_company=text("to_company"), regarding=text("regarding"), comments=text("comments"),
        to_location=text("to_location"), to_voicenumber=text("to_voicenumber"), to_address=text("to_address"),
        to_zip=text("to_zip"), to_city=text("to_city"), tsi=text("user_tsi"), coverpage=bool(text("coverpage")),
        whichcover=text("whichcover"), notify_requeue=bool(text("notify_requeue")), priority=text("priority") or "*",
        numtries=text("numtries"), killtime=text("killtime"), killtime_unit=text("killtime_unit") or "hours",
        sendtime=bool(text("sendtime")), sendtime_hour=text("sendtimeHour"), sendtime_min=text("sendtimeMin"))


@view_config(route_name="sendfax", renderer="namifax:templates/sendfax.jinja2", permission="send_fax")
def sendfax_view(request):
    """Render the Send Fax form, or submit it to HylaFAX (the original sendfax.php / refax.php)."""
    identity = request.identity or {"username": "admin", "is_admin": True}
    sender, account = _account(request)
    cover_list, default_cover = _covers(request, account)
    access = fax_access(request)
    superuser = bool(access.superuser)
    lines = _lines(request, account)

    def page(form_data, error=None, original_fid=None):
        return {
            "title": "- NamiFAX - Send Fax", "current_user": identity, "active_tab": "sendfax", "error": error,
            "form_data": form_data, "cover_list": cover_list,
            "default_cover": default_cover, "original_fid": original_fid,
            "priority_list": ["*"] + [str(n) for n in range(0, 255, 10)],
            "hours": [f"{n:02d}" for n in range(24)], "minutes": [f"{n:02d}" for n in range(60)],
            "default_tsi": account.get("user_tsi") or "", "lines": lines, "superuser": superuser,
            "max_upload": upload_check.max_label(), "max_upload_bytes": upload_check.max_bytes(),
        }

    # "Reply to fax": the fax being answered must exist and the user must have the right to it, else the plain page
    original = None
    refax = request.params.get("refax")
    if refax:
        original = ArchiveIn(db=request.dbsession)
        if not load_fax(request, original, refax, action="refax"):
            return HTTPFound(location=request.route_url("sendfax"))
    original_fid = original.get_fid() if original is not None else None

    if request.method != "POST":
        form = {"coverpage": "1" if settings.sendfax_use_coverpage() else "",
                "notify_requeue": "1" if settings.sendfax_requeue_email() else ""}
        if original is not None:
            form["faxnumber"] = _sender_number(request, original)
        return page(form, original_fid=original_fid)

    params = request.params
    if not lines:
        return page(params, str(_("No modems configured")), original_fid)
    if not (params.get("faxnumber") or params.get("destinations") or "").strip():
        return page(params, "Fax number is required", original_fid)

    modem = (params.get("modem") or "").strip()
    devices = [d for d, _label in lines if d]
    if modem and modem not in devices:
        return page(params, str(_("You may not use this line.")), original_fid)
    if not modem and not any(d == "" for d, _label in lines):
        modem = devices[0]                                      # no 'any line' right: the first (usually only) line

    files: list[str] = [original.get_pdfpath()] if original is not None and original.get_pdfpath() else []
    uploaded: list[str] = []
    problem = None
    for item in request.POST.getall("file"):
        if hasattr(item, "file") and getattr(item, "filename", ""):
            head = item.file.read(upload_check.HEAD)
            item.file.seek(0, os.SEEK_END)
            size = item.file.tell()
            item.file.seek(0)
            problem = upload_check.check(head, size)
            if problem:
                problem = f"{_(problem)} ({item.filename})"
                break
            dest_path = os.path.join(tempfile.gettempdir(), f"sendfax_{uuid.uuid4().hex[:8]}_{os.path.basename(item.filename)}")
            with open(dest_path, "wb") as out:
                shutil.copyfileobj(item.file, out)
            uploaded.append(dest_path)
    if problem:
        for path in uploaded:
            try:
                os.remove(path)
            except OSError:
                pass
        return page(params, problem, original_fid)

    send = _send_request(params, files + uploaded)
    send.modem = modem or None
    if not superuser:                                           # priority and TSI belong to superusers
        send.priority = "*"
        send.tsi = str(account.get("user_tsi") or "")
    try:
        result = dispatch_sendfax(send, sender)
    finally:
        for path in uploaded:
            try:
                os.remove(path)
            except OSError:
                pass
    if not result.get("success"):
        return page(params, result.get("error", "Failed to dispatch fax"), original_fid)
    request.session.flash(
        str(_("Your fax has been successfully queued to be faxed.")) + (f" ({_('Job')} {result['jobid']})" if result.get("jobid") else ""),
        "fax")
    return HTTPFound(location=request.route_url("outbox"))
