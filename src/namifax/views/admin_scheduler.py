"""Admin > Scheduled Tasks: which maintenance jobs run, when, with which days; run one now; how the last run went."""

from __future__ import annotations

from datetime import datetime

from pyramid.renderers import render
from pyramid.response import Response
from pyramid.view import view_config

from namifax.i18n import _
from namifax.services import scheduler_config as cfg
from namifax.services import scheduler as engine
from namifax.services.scheduler import NamiFaxScheduler, get_scheduler, launch, request_stop
from namifax.services.system_config import SystemConfigService


THREADED = True        # "Run now" runs in a thread so that the page can show it running (tests run it inline)


def _read(post, current: cfg.JobSettings) -> tuple[cfg.JobSettings, list[str]]:
    """The settings from the form; a time that is not ``HH:MM`` keeps the old value and is reported."""
    problems: list[str] = []

    def time(name: str, old: str) -> str:
        raw = post.get(name, "")
        clean = cfg.clean_time(raw, "")
        if not clean:
            problems.append(f"{raw!r}")
            return old
        return clean

    def number(name: str, old: int) -> int:
        raw = (post.get(name) or "").strip()
        return int(raw) if raw.isdecimal() else old

    updated = cfg.JobSettings(
        tmp_enabled="tmp_enabled" in post, tmp_time=time("tmp_time", current.tmp_time), tmp_days=number("tmp_days", current.tmp_days),
        inbox_enabled="inbox_enabled" in post, inbox_time=time("inbox_time", current.inbox_time),
        inbox_days=number("inbox_days", current.inbox_days),
        lifecycle_enabled="lifecycle_enabled" in post, lifecycle_time=time("lifecycle_time", current.lifecycle_time),
        phonebook_enabled="phonebook_enabled" in post, phonebook_minutes=number("phonebook_minutes", current.phonebook_minutes),
    )
    return updated, problems


def _state(session) -> dict:
    """What the state box shows: what an administrator asked for (the buttons) and what the scheduler has done about it so far."""
    seen = cfg.heartbeat(session)
    asked_stop = cfg.stopped(session)
    engine = cfg.engine_state(session)
    alive = cfg.alive(session)
    if not alive:
        phase = "none"
    elif asked_stop:
        phase = "stopped" if engine == "stopped" else "stopping"
    else:
        phase = "running" if engine == "running" else "starting"
    return {"alive": alive, "asked_stop": asked_stop, "phase": phase,
            "seen_ago": int((datetime.now() - seen).total_seconds()) if seen else None}


def _jobs_html(request, session) -> dict:
    """The status block (last result, Run now or Stop) of every job."""
    html = {}
    for job in cfg.JOBS:
        handle = engine.running_handle(job)
        marker = None if handle else cfg.running_marker(session, job)
        running = handle is not None or marker is not None
        started = handle.started.strftime("%Y-%m-%d %H:%M:%S") if handle else (marker or {}).get("started")
        html[job] = render("namifax:templates/admin_scheduler_job.jinja2", {
            "job": job, "running": running, "started": started, "by": handle.by if handle else (marker or {}).get("by"),
            "stopping": bool(running and ((handle and handle.cancel.is_set()) or cfg.cancel_requested(session, job))),
            "last": cfg.last_run(session, job)}, request=request)
    return html


@view_config(route_name="admin_scheduler_jobs", permission="admin")
def admin_scheduler_jobs_view(request):
    """The job status blocks alone, for the page to refresh while a job runs."""
    blocks = _jobs_html(request, request.dbsession)
    body = "".join(blocks.values())
    return Response(body, content_type="text/html", charset="utf-8")


def _fragment(request, session) -> str:
    return render("namifax:templates/admin_scheduler_state.jinja2", {"st": _state(session)}, request=request)


@view_config(route_name="admin_scheduler_state", permission="admin")
def admin_scheduler_state_view(request):
    """The state box alone, for the page to refresh without reloading."""
    return Response(_fragment(request, request.dbsession), content_type="text/html", charset="utf-8")


@view_config(route_name="admin_scheduler", renderer="namifax:templates/admin_scheduler.jinja2", permission="admin")
def admin_scheduler_view(request):
    """The scheduled tasks page."""
    session = request.dbsession
    message = error = None
    current = cfg.load(session)

    if request.method == "POST":
        action = request.POST.get("action")
        if action in ("stop", "start"):
            cfg.set_stopped(session, action == "stop")
            hosted = get_scheduler()
            if hosted.is_running:                          # this process hosts the scheduler: act at once, do not wait for the next check
                hosted.watch_config(session)
            message = (_("The scheduler was stopped. Nothing runs by itself until it is started again; Run now still works.")
                       if action == "stop" else _("The scheduler was started."))
        elif action == "run":
            job = request.POST.get("job", "")
            if job not in cfg.JOBS:
                error = _("Unknown task.")
            elif engine.is_running(job, session):
                error = _("This task is already running.")
            else:
                launch(job, "manual", background=THREADED, session=None if THREADED else session)
        elif action == "stop_job":
            job = request.POST.get("job", "")
            if job in cfg.JOBS and request_stop(job, session):
                message = _("The task was asked to stop; it stops at the next safe point.")
        else:
            updated, bad = _read(request.POST, current)
            cfg.save(session, updated)
            current = cfg.load(session)
            if bad:
                error = _("A time must be written HH:MM (24 hours); the old time was kept.") + " " + ", ".join(bad)
            else:
                message = _("Scheduled tasks saved. A running scheduler picks the change up within a minute.")

    if request.method == "POST" and request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return Response(_fragment(request, session), content_type="text/html", charset="utf-8")

    store = SystemConfigService(session)
    return {
        "title": "NamiFAX - Admin - Scheduled Tasks",
        "current_user": request.identity,
        "active_tab": "admin",
        "active_admin": "scheduler",
        "s": current,
        "job_html": _jobs_html(request, session),
        "state_html": _fragment(request, session),
        "policy": {"tiff_days": store.get("storage_purge_tiff_days", ""), "keep_days": store.get("storage_retention_days", "")},
        "message": message,
        "error": error,
    }
