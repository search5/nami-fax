"""NamiFAX Outbox View (the original outbox.php)."""

from __future__ import annotations

from pyramid.csrf import check_csrf_token
from pyramid.view import view_config

from namifax.i18n import _
from namifax.services.addressbook import NFAddressBook
from namifax.services.faxqueue import FaxQueue
from namifax.views.admin import get_all_admin_modems
from namifax.views.fax_rights import fax_access


def _visible(queue: FaxQueue, access) -> list[dict]:
    """A superuser sees every job; anybody else only their own and those sent for them by mail."""
    return queue.get_queue() if access.superuser else queue.list_owner(access.username)


def _with_companies(request, jobs: list[dict]) -> list[dict]:
    """Name the company of each job's number (the number itself when the address book does not know it)."""
    book = NFAddressBook(db=request.dbsession)
    rows = []
    for job in jobs:
        row = dict(job, company=job.get("number", ""))
        try:
            found, _multiple = book.loadbyfaxnum(job.get("number", ""))
            if found and book.get_company():
                row["company"] = book.get_company()
        except Exception:
            pass
        rows.append(row)
    return rows


@view_config(route_name="outbox", renderer="namifax:templates/outbox.jinja2", permission="view")
def outbox_view(request):
    """The fax queue: waiting and sending jobs, and failed ones, each with its own modify/kill buttons."""
    identity = request.identity or {"username": "admin", "is_admin": True}
    access = fax_access(request)
    fq = FaxQueue(auto_process=False, db=request.dbsession)
    flash_message = next(iter(request.session.pop_flash("fax")), None)       # what the Send Fax page left for us

    # Killing changes the queue, so it only happens for a POST that carries this session's CSRF token. (The original
    # used a plain link, which any other web page could have made a signed-in user follow.)
    kill = (request.POST.get("kill") or "").strip() if request.method == "POST" else ""
    if kill:
        if check_csrf_token(request, raises=False):
            flash_message = _kill(fq, access, kill)
        else:
            flash_message = _("Your session has expired. Reload the page and try again.")

    fq.process_queue()
    jobs = _with_companies(request, _visible(fq, access))
    fq.process_failed_queue()
    failed_jobs = _with_companies(request, _visible(fq, access))

    return {
        "title": "- NamiFAX - Outbox",
        "current_user": identity,
        "active_tab": "outbox",
        "jobs": jobs,
        "failed_jobs": failed_jobs,
        "num_outbox": len(jobs),
        "queue_count": len(jobs) + len(failed_jobs),
        "flash_message": flash_message,
        "csrf_token": request.session.get_csrf_token(),
        "modem_list": get_all_admin_modems(request.dbsession),
    }


def _kill(fq: FaxQueue, access, jid: str) -> str:
    """Remove a job, but only one the user may see (waiting, else failed), in the name of the job's owner."""
    if not (jid.isdecimal() and len(jid) <= 8):
        return _("Invalid job number.")
    for load in (fq.process_queue, fq.process_failed_queue):
        load()
        job = next((j for j in _visible(fq, access) if j.get("jid") == jid), None)
        if job:
            if fq.killjob(job.get("owner", ""), int(jid)):
                return f"Job #{jid} successfully killed"
            return f"Failed to kill job #{jid}"
    return f"Job #{jid} was not found in your queue"
