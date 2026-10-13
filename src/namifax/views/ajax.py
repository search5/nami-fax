"""NamiFAX asynchronous AJAX API views matching legacy ajax/*.php."""

import html
import os
from pyramid.httpexceptions import HTTPFound, HTTPForbidden
from pyramid.response import Response
from pyramid.view import view_config

from namifax.common import settings
from namifax.i18n import _
from namifax.services.addressbook import NFAddressBook
from namifax.services.archive_in import ArchiveIn
from namifax.services.distro import DistributionList
from namifax.services.faxqueue import FaxQueue
from namifax.services.modem import FaxModem
from namifax.views.admin import get_all_admin_modems
from namifax.views.fax_rights import fax_access, load_fax


@view_config(route_name="ajax_modemstatus", permission="view")
def ajax_modem_status(request):
    """Modem status for the poller (the original ajaxmodemstatus.php): the modems named in ``modems=a,b``, or all of the user's.

    A user is only told about the modems on their account (a superuser about every configured one).
    """
    access = fax_access(request)
    fm = FaxModem(db=request.dbsession)
    allowed = (fm.get_modems() if access.superuser else access.modems) or []
    asked = [m.strip() for m in (request.params.get("modems") or "").split(",") if m.strip()]
    devices = [m for m in asked if m in allowed] if asked else list(allowed)

    rows_xml = []
    for dev in devices:
        if fm.load_device(dev):
            st = fm.get_status() or {}
            rows_xml.append(
                f"  <row>\n"
                f"    <modem>{html.escape(str(dev))}</modem>\n"
                f"    <status>{html.escape(str(st.get('status', '')))}</status>\n"
                f"    <class>{html.escape(str(st.get('class', '')))}</class>\n"
                f"  </row>"
            )

    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<response>\n' + "\n".join(rows_xml) + ("\n" if rows_xml else "") + "</response>"
    return Response(xml_content, content_type="text/xml")


def audio_dir() -> str:
    return os.environ.get("AVANTFAX_AUDIO_DIR") or os.path.join(os.path.dirname(os.path.dirname(__file__)), "audio")


def _user_sound(request) -> str:
    """The file name of the user's new-fax sound when it exists, else an empty string."""
    from sqlalchemy import select

    from namifax.models import UserAccount

    who = request.identity or {}
    uid = who.get("user_id") or who.get("uid")
    if not uid:
        return ""
    chosen = request.dbsession.execute(select(UserAccount.audiofile).where(UserAccount.uid == uid)).scalar()
    name = os.path.basename(chosen or "")
    return name if name and os.path.isfile(os.path.join(audio_dir(), name)) else ""


@view_config(route_name="audio", permission="view")
def audio_view(request):
    """A sound file for the new-fax notification (only plain files of the sound folder)."""
    import mimetypes

    from pyramid.httpexceptions import HTTPNotFound
    from pyramid.response import FileResponse

    name = request.matchdict.get("name", "")
    if name != os.path.basename(name) or name.startswith("."):
        raise HTTPNotFound()
    path = os.path.join(audio_dir(), name)
    if not os.path.isfile(path):
        raise HTTPNotFound()
    return FileResponse(path, request=request, content_type=mimetypes.guess_type(name)[0] or "audio/wav")


@view_config(route_name="ajax_inbox", permission="view")
def ajax_inbox_count(request):
    """Unread inbox count poller matching legacy ajaxinbox.php."""
    arc = ArchiveIn(db=request.dbsession)
    count = 0
    try:
        access = fax_access(request)
        count = arc.get_num_faxes(access.devices, access.categories, access.did_routing) or 0
    except Exception:
        count = 0
    answer = str(count)
    sound = _user_sound(request)
    if sound:
        answer += f"|{sound}"                                      # the original appends the user's sound file to the count
    return Response(answer, content_type="text/plain")


@view_config(route_name="ajax_book", permission="view")
def ajax_addressbook_suggest(request):
    """Address book auto-suggest matching legacy ajaxbook.php."""
    q = (request.params.get("q") or request.GET.get("q") or "").strip()
    ab = NFAddressBook(db=request.dbsession)
    rows_xml = []

    try:
        companies = [] if not settings.contact_lookup_allowed(q) else (ab.search_companies(q) if q else ab.get_companies())
        numbers = ab.numbers_by_company() if companies else {}
        for c in companies or []:
            cid = c.get("abook_id")
            for number in numbers.get(cid, []):                 # one row per fax number, like the original
                label = c.get("company") or ""
                if number.get("description"):
                    label += f" ({number['description']})"
                faxnum = number.get("faxnumber") or ""
                rows_xml.append(
                    f"  <row>\n"
                    f"    <company>{html.escape(f'{label} - {faxnum}')}</company>\n"
                    f"    <cid>{cid}</cid>\n"
                    f"    <faxnum>{html.escape(faxnum)}</faxnum>\n"
                    f"    <fnid>{number.get('abookfax_id')}</fnid>\n"
                    f"  </row>"
                )
    except Exception:
        pass

    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<response>\n' + "\n".join(rows_xml) + ("\n" if rows_xml else "") + "</response>"
    return Response(xml_content, content_type="text/xml")


@view_config(route_name="ajax_emailbook", permission="view")
def ajax_emailbook_suggest(request):
    """Email address auto-suggest matching legacy ajaxemailbook.php."""
    q = (request.params.get("q") or request.GET.get("q") or "").strip().lower()
    ab = NFAddressBook(db=request.dbsession)
    rows_xml = []

    try:
        contacts = ab.get_contacts()
        if contacts:
            for eid, cstr in contacts.items():
                email = cstr.split("<")[1].replace(">", "").strip() if "<" in cstr else cstr
                if not q or q in email.lower() or q in cstr.lower():
                    rows_xml.append(
                        f"  <row>\n"
                        f"    <id>{eid}</id>\n"
                        f"    <email>{html.escape(email)}</email>\n"
                        f"  </row>"
                    )
    except Exception:
        pass

    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<response>\n' + "\n".join(rows_xml) + ("\n" if rows_xml else "") + "</response>"
    return Response(xml_content, content_type="text/xml")


@view_config(route_name="ajax_prefillto", permission="view")
def ajax_addressbook_prefill(request):
    """Address book contact info prefill matching legacy ajaxprefillto.php."""
    fnid = request.GET.get("fnid", "").strip()
    ab = NFAddressBook(db=request.dbsession)
    to_company = ""
    to_person = ""
    to_address = ""
    to_zip = ""
    to_city = ""
    to_location = ""
    to_voicenumber = ""

    try:
        if fnid.isdecimal():
            fid_int = int(fnid)
            if ab.loadbyfaxnumid(fid_int):
                to_company = ab.get_company() or ""
                to_person = ab.get_to_person() or ""
                to_address = ab.get_to_address() or ""
                to_zip = ab.get_to_zip() or ""
                to_city = ab.get_to_city() or ""
                to_location = ab.get_to_location() or ""
                to_voicenumber = ab.get_to_voicenumber() or ""
            elif ab.loadbycid(fid_int):
                to_company = ab.get_company() or ""
    except Exception:
        pass

    xml_content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<response>\n"
        "  <row>\n"
        f"    <to_company>{html.escape(str(to_company))}</to_company>\n"
        f"    <to_person>{html.escape(str(to_person))}</to_person>\n"
        f"    <to_address>{html.escape(str(to_address))}</to_address>\n"
        f"    <to_zip>{html.escape(str(to_zip))}</to_zip>\n"
        f"    <to_city>{html.escape(str(to_city))}</to_city>\n"
        f"    <to_location>{html.escape(str(to_location))}</to_location>\n"
        f"    <to_voicenumber>{html.escape(str(to_voicenumber))}</to_voicenumber>\n"
        "  </row>\n"
        "</response>"
    )
    return Response(xml_content, content_type="text/xml")


@view_config(route_name="ajax_dlist", permission="view")
def ajax_distrolist_faxes(request):
    """Distribution list fax numbers matching legacy ajaxdlist.php."""
    dl_id = request.GET.get("dl_id", "").strip()
    dl = DistributionList(db=request.dbsession)
    faxes_str = "Invalid list id"

    try:
        if dl_id.isdecimal() and dl.load_list(int(dl_id)):
            numbers = [e.split("|", 1)[1] for e in dl.list_entries() if "|" in e]      # entries are "<id>|<number>"
            faxes_str = "; ".join(numbers)
    except Exception:
        pass

    return Response(faxes_str, content_type="text/plain")


def _fids(request) -> list[int]:
    """The fax numbers a request names: checkboxes (``fids=1&fids=2``) and/or the original's ``fids=1,2``."""
    def all_of(name):
        getall = getattr(request.params, "getall", None)            # (a plain dict has no getall)
        return getall(name) if getall else ([request.params[name]] if name in request.params else [])

    values = all_of("fids") + all_of("fid")
    return [int(v) for raw in values for v in str(raw).split(",") if v.strip().isdecimal()]


def _done(request):
    """What follows a batch action: an empty answer for script callers, the inbox for a page."""
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return Response("", status_code=200)
    following = str(request.params.get("next") or "").strip()              # the viewer goes on to the next fax
    if following.isdecimal():
        return HTTPFound(location=request.route_url("viewfax", _query={"fid": following}))
    return HTTPFound(location=request.route_url("inbox"))


@view_config(route_name="ajax_archivefax", request_method="POST", permission="view")
def ajax_archive_fax(request):
    """Archive faxes (the original ajaxarchivefax.php): only those the user may use."""
    arc = ArchiveIn(db=request.dbsession)
    for fid in _fids(request):
        if load_fax(request, arc, fid, action="ajaxarchivefax"):
            arc.set_archivebox(fid)
    return _done(request)


@view_config(route_name="ajax_faxalter", renderer="namifax:templates/faxalter.jinja2", permission="view")
def ajax_faxalter(request):
    """Modify or resubmit a queued fax job (the original ajax/faxalter.php).

    The fields become faxalter operations in the original's order. The job is altered in the name of the signed-in user;
    only a superuser may name another owner (the original took any owner from the request, so anybody could alter any job).
    """
    access = fax_access(request)
    params = request.POST if request.method == "POST" else request.params
    resubmit = bool(params.get("resubmit") or params.get("r"))
    jid = (params.get("jid") or "").strip()
    owner = (params.get("owner") or "").strip() if access.superuser else ""
    owner = owner or access.username or (request.identity or {}).get("username", "")

    modems = FaxModem(db=request.dbsession)
    devices = (access.configured_modems if access.superuser else access.modems) or []
    modem_list = []
    for device in devices:
        if modems.load_device(device):
            modem_list.append((device, modems.get_alias() or device))

    def text(name: str, default: str = "") -> str:
        return (params.get(name) or default).strip()

    values = {"jid": jid, "owner": owner, "resubmit": "1" if resubmit else "", "destination": text("destination"),
              "priority": text("priority", "*"), "modem": text("modem"), "numtries": text("numtries"),
              "killtime": text("killtime", "3" if resubmit and request.method != "POST" else ""),
              "killtime_unit": text("killtime_unit", "hours"), "sendnow": bool(text("sendnow")),
              "sendtime": bool(text("sendtime")), "sendtimeHour": text("sendtimeHour"), "sendtimeMin": text("sendtimeMin")}

    def page(error=None):
        return {"title": "- NamiFAX - Modify Fax Job", "values": values, "error": error, "modem_list": modem_list,
                "priority_list": ["*"] + [str(n) for n in range(0, 255, 10)],
                "hours": [f"{n:02d}" for n in range(24)], "minutes": [f"{n:02d}" for n in range(60)]}

    if request.method != "POST":
        return page()

    if not (jid.isdecimal() and (not values["killtime"] or values["killtime"].isdecimal())
            and (not values["numtries"] or values["numtries"].isdecimal())):
        return page(_("Please enter a valid number."))

    operations: dict = {}
    if values["destination"]:
        operations["destination"] = values["destination"]
    if values["numtries"]:
        operations["tries"] = values["numtries"]
    if values["modem"]:
        operations["device"] = values["modem"]
    if values["priority"] != "*":
        operations["priority"] = values["priority"]
    if values["sendtime"] and values["sendtimeHour"] and values["sendtimeMin"]:
        operations["sendtime"] = f"{values['sendtimeHour']}:{values['sendtimeMin']}"
    if values["killtime"]:
        operations["killtime"] = f"now + {values['killtime']} {values['killtime_unit']}"
    if values["sendnow"]:
        operations["sendtime"] = "now"
    if resubmit:
        operations["resubmit"] = True

    FaxQueue(db=request.dbsession).faxalter(owner, int(jid), operations)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return Response("", status_code=200)
    return HTTPFound(location=request.route_url("outbox"))


@view_config(route_name="ajax_deletefaxes", renderer="namifax:templates/batch_delete.jinja2", permission="view")
def ajax_deletefaxes_view(request):
    """Delete faxes after asking (the original ajaxdeletefaxes.php): only those the user may delete."""
    access = fax_access(request)
    if not (access.can_del or access.superuser):
        raise HTTPForbidden("You may not delete faxes.")
    fids = _fids(request)
    if request.method == "POST":
        arc = ArchiveIn(db=request.dbsession)
        for fid in fids:
            if load_fax(request, arc, fid, action="ajaxdeletefaxes", delete=True):
                arc.delete_fax()
        return _done(request)
    return {"title": "- NamiFAX - Delete Faxes", "fids": fids}


@view_config(route_name="ajax_archivebook", permission="view")
def ajax_archivebook_view(request):
    """Address book company auto-suggest matching legacy ajax/archivebook.php."""
    q = (request.params.get("q") or request.GET.get("q") or "").strip()
    ab = NFAddressBook(db=request.dbsession)
    rows_xml = []

    try:
        companies = [] if not settings.contact_lookup_allowed(q) else (ab.search_companies(q) if q else ab.get_companies())
        if companies:
            for c in companies:
                cid = c.get("ab_id") or c.get("abook_id") or 1
                cname = c.get("company", "")
                rows_xml.append(
                    f"  <row>\n"
                    f"    <company>{html.escape(cname)}</company>\n"
                    f"    <cid>{cid}</cid>\n"
                    f"  </row>"
                )
    except Exception:
        pass

    if rows_xml:
        xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<response>\n' + "\n".join(rows_xml) + "\n</response>"
    else:
        xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<response></response>'
    return Response(xml_content, content_type="text/xml")



