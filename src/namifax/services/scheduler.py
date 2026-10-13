"""NamiFAX Scheduler Service managing periodic maintenance jobs using APScheduler.

Replaces OS-level crontab with in-process or standalone scheduling.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

# Ensure src directory is on sys.path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from namifax.cli.cron import run_cron
from namifax.cli.phb import export_phonebook_count
from namifax.db.provider import cli_session
from namifax.services import scheduler_config as cfg
from namifax.services.archive_in import ArchiveIn
from namifax.services.job_control import JobStopped  # noqa: F401  (re-exported)

logger = logging.getLogger("namifax.scheduler")


@dataclass
class JobHandle:
    """A job that is running in this process."""

    name: str
    by: str
    started: datetime = field(default_factory=datetime.now)
    cancel: threading.Event = field(default_factory=threading.Event)


_RUNNING: dict[str, JobHandle] = {}
_RUNNING_LOCK = threading.Lock()


def claim(name: str, by: str = "schedule") -> Optional[JobHandle]:
    """Reserve a job for running; None when it is already running here (a job never runs twice at once)."""
    with _RUNNING_LOCK:
        if name in _RUNNING:
            return None
        handle = _RUNNING[name] = JobHandle(name, by)
        return handle


def release(handle: JobHandle) -> None:
    with _RUNNING_LOCK:
        if _RUNNING.get(handle.name) is handle:
            del _RUNNING[handle.name]


def running_handle(name: str) -> Optional[JobHandle]:
    return _RUNNING.get(name)


def is_running(name: str, session=None) -> bool:
    """Is the job running - in this process, or (when a ``session`` is given) in another one that left a fresh marker?"""
    if name in _RUNNING:
        return True
    return bool(session is not None and cfg.running_marker(session, name))


def request_stop(name: str, session=None) -> bool:
    """Ask a running job to stop at its next safe point. Returns whether there was a job to ask."""
    handle = _RUNNING.get(name)
    if handle is not None:
        handle.cancel.set()
    elif session is None or not cfg.running_marker(session, name):
        return False
    if session is not None:
        cfg.request_cancel(session, name)             # (a job in another process reads this)
    return True


def launch(name: str, by: str = "manual", background: bool = True, session=None) -> Optional[JobHandle]:
    """Start a job now: reserved at once (so the page can show it running), executed in a thread unless ``background`` is false."""
    handle = claim(name, by)
    if handle is None:
        return None
    scheduler = NamiFaxScheduler()
    if background:
        threading.Thread(target=scheduler.run_job, args=(name, None, by, handle), daemon=True, name=f"namifax-job-{name}").start()
    else:
        scheduler.run_job(name, session, by, handle)
    return handle


class NamiFaxScheduler:
    """Integrated task scheduler using APScheduler with threading fallback."""

    def __init__(self, tmp_clean_days: int = 1, phonebook_sync_interval_mins: int = 60) -> None:
        self.tmp_clean_days = tmp_clean_days
        self.phonebook_sync_interval_mins = phonebook_sync_interval_mins
        self.is_running = False
        self._scheduler = None
        self._fallback_threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

    # --- the jobs -----------------------------------------------------------------------------------------------------

    def run_job(self, name: str, session=None, by: str = "schedule", handle: Optional[JobHandle] = None) -> dict:
        """Run one job now (on a schedule or from the admin page) and remember how it went; never raises.

        Returns ``{"ok", "summary", "at", "stopped"}``. ``session`` is used when given, else the job opens its own on the configured
        database. A job that is already running is not started again. ``handle`` is a reservation made by ``claim``/``launch``.
        While it runs the job can be asked to stop (``request_stop``); it stops at its next safe point and the result says so.
        """
        if name not in cfg.JOBS:
            raise ValueError(f"unknown job: {name}")
        handle = handle or claim(name, by)
        if handle is None:
            return {"ok": False, "stopped": False, "summary": "already running", "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        owns_session = session is None
        try:
            if owns_session:
                with cli_session(ensure_schema=True) as opened:
                    return self._run_claimed(name, opened, handle, commit=True)
            return self._run_claimed(name, session, handle, commit=False)
        finally:
            release(handle)

    def _run_claimed(self, name: str, session, handle: JobHandle, commit: bool) -> dict:
        settings = cfg.load(session)
        # Another process on the same database (a second web service) may be running this job: its marker is fresh.
        # Checked before our own marker is written, and we hold the in-process claim, so the marker is never our own.
        if cfg.running_marker(session, name):
            return {"ok": False, "stopped": False, "summary": "already running", "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        cfg.mark_running(session, name, handle.by)
        cfg.clear_cancel(session, name)
        if commit:
            session.commit()
        last_check = [0.0]

        def should_stop() -> bool:
            if handle.cancel.is_set():
                return True
            if time.monotonic() - last_check[0] > 1.0:                      # a Stop asked in another process: look about once a second
                last_check[0] = time.monotonic()
                if cfg.cancel_requested(session, name):
                    handle.cancel.set()
            return handle.cancel.is_set()

        stopped = False
        try:
            if name == "tmp":
                run_cron(["cron", "-t", str(settings.tmp_days)], db=session, should_stop=should_stop)
                summary = f"temporary files older than {settings.tmp_days} day(s) removed"
            elif name == "inbox":
                moved = ArchiveIn(db=session).prune_inbox(settings.inbox_days, should_stop=should_stop)
                summary = f"{moved} fax(es) older than {settings.inbox_days} day(s) moved to the archive"
            elif name == "lifecycle":
                from namifax.services.storage_lifecycle import StorageLifecycleService

                result = StorageLifecycleService(db=session).run_saved_policy(should_stop=should_stop)
                summary = ("no policy saved on the Storage page: nothing was removed" if result is None else
                           f"{result.get('tiffs_purged', 0)} TIFF file(s) and {result.get('faxes_purged', 0)} fax(es) removed")
            else:
                summary = f"phonebook exported ({export_phonebook_count(db=session, should_stop=should_stop)} entries)"
            ok = True
            if handle.cancel.is_set():
                stopped, summary = True, f"stopped by an administrator; {summary.split(' (')[0] if name == 'phonebook' else summary}"
        except JobStopped:
            ok, stopped, summary = True, True, "stopped by an administrator before anything was written"
        except Exception as exc:                                      # a failed job is a result, not a crash of the scheduler
            logger.error("[Scheduler] job %s failed: %s", name, exc, exc_info=True)
            ok, summary = False, f"failed: {exc}"
        result = cfg.record_run(session, name, ok, summary, stopped=stopped)
        cfg.clear_running(session, name)
        cfg.clear_cancel(session, name)
        try:
            from namifax.common.helpers import avantfaxlog

            avantfaxlog(f"scheduler> {name}: {summary}", echo=False, session=session)
        except Exception:
            pass
        if commit:
            session.commit()
        return result

    def _scheduled(self, name: str) -> None:
        self.run_job(name)

    # --- following the saved settings ---------------------------------------------------------------------------------

    config_signature: str = ""

    @property
    def engine_running(self) -> bool:
        """Is the APScheduler engine itself running (jobs can fire)?"""
        return self._scheduler is not None and bool(getattr(self._scheduler, "running", False))

    def apply_config(self, session=None) -> None:
        """(Re)schedule every job from the saved settings; a job that is switched off is removed."""
        if self._scheduler is None:
            return
        if session is None:
            with cli_session(ensure_schema=True) as opened:
                return self.apply_config(opened)

        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger

        s = cfg.load(session)
        wanted = {}
        for name, enabled, at in (("tmp", s.tmp_enabled, s.tmp_time), ("inbox", s.inbox_enabled, s.inbox_time),
                                  ("lifecycle", s.lifecycle_enabled, s.lifecycle_time)):
            if enabled:
                hour, minute = at.split(":")
                wanted[name] = CronTrigger(hour=int(hour), minute=int(minute))
        if s.phonebook_enabled:
            wanted["phonebook"] = IntervalTrigger(minutes=s.phonebook_minutes)
        for name in cfg.JOBS:
            if name in wanted:
                self._scheduler.add_job(self._scheduled, trigger=wanted[name], args=[name], id=name, name=name,
                                        replace_existing=True, misfire_grace_time=3600, coalesce=True)
            elif self._scheduler.get_job(name):
                self._scheduler.remove_job(name)
        self.config_signature = cfg.signature(session)

    # --- the APScheduler engine: started and shut down as the administrator asks ----------------------------------------

    def start_engine(self, session=None) -> None:
        """Create and start the APScheduler engine with the saved jobs."""
        if self.engine_running:
            return
        from apscheduler.schedulers.background import BackgroundScheduler

        self._scheduler = BackgroundScheduler()
        self._scheduler.start()
        try:
            self.apply_config(session)
        except Exception as exc:
            logger.error("[Scheduler] could not read the saved settings: %s", exc)
        logger.info("[Scheduler] APScheduler engine started.")

    def stop_engine(self) -> None:
        """Shut the APScheduler engine down: no job fires until it is started again."""
        engine, self._scheduler = self._scheduler, None
        if engine is not None:
            try:
                engine.shutdown(wait=False)
            except Exception:
                pass
            logger.info("[Scheduler] APScheduler engine stopped.")

    def watch_config(self, session=None) -> bool:
        """The controller's turn: say we are alive, start or stop the engine as asked, follow changed settings.

        True when the engine was started or stopped or the jobs were rescheduled.
        """
        if session is None:
            with cli_session(ensure_schema=True) as opened:
                return self.watch_config(opened)
        changed = False
        want_running = not cfg.stopped(session)
        if want_running and not self.engine_running:
            self.start_engine(session)
            changed = True
        elif not want_running and self.engine_running:
            self.stop_engine()
            changed = True
        elif self.engine_running and cfg.signature(session) != self.config_signature:
            self.apply_config(session)
            changed = True
        cfg.beat(session, "running" if self.engine_running else "stopped")
        return changed

    def _control_loop(self) -> None:
        while not self._stop_event.wait(self.control_interval):
            try:
                self.watch_config()
            except Exception as exc:
                logger.error("[Scheduler] controller check failed: %s", exc)

    def job_phonebook_sync(self) -> None:
        """Execute periodic address book to HylaFAX PBOOK1.1 synchronization."""
        self.run_job("phonebook")

    control_interval = 15            # seconds between the controller's checks (it hears a Stop/Start within this time)
    _control_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the scheduler: the controller thread, and the APScheduler engine unless an administrator stopped it.

        It runs inside the web process (``namifax serve``). A Stop on the admin page shuts only the engine down; the controller
        stays so that a Start can bring it back.
        """
        if self.is_running:
            return
        self._stop_event.clear()
        self.is_running = True

        try:
            import apscheduler  # noqa: F401
        except ImportError:                                                  # a plain thread timer when APScheduler is missing
            logger.warning("[Scheduler] APScheduler not installed; using built-in thread timer.")

            def _runner():
                while not self._stop_event.wait(self.phonebook_sync_interval_mins * 60):
                    self.job_phonebook_sync()

            t = threading.Thread(target=_runner, daemon=True, name="NamiFaxSchedulerFallback")
            t.start()
            self._fallback_threads.append(t)
        else:
            try:
                with cli_session(ensure_schema=True) as session:
                    if not cfg.stopped(session):
                        self.start_engine(session)
                    cfg.beat(session, "running" if self.engine_running else "stopped")
            except Exception as exc:                                         # no database yet: run with the defaults
                logger.error("[Scheduler] could not read the saved settings: %s", exc)
                if not self.engine_running:
                    self.start_engine_without_settings()
            self._control_thread = threading.Thread(target=self._control_loop, daemon=True, name="NamiFaxSchedulerControl")
            self._control_thread.start()

    def start_engine_without_settings(self) -> None:
        from apscheduler.schedulers.background import BackgroundScheduler

        self._scheduler = BackgroundScheduler()
        self._scheduler.start()

    def stop(self) -> None:
        """Stop everything: the engine and the controller (the process is meant to end)."""
        if not self.is_running:
            return
        self._stop_event.set()
        self.stop_engine()
        thread = self._control_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5)
        self._control_thread = None
        self.is_running = False
        logger.info("[Scheduler] Scheduler stopped.")


_global_scheduler: Optional[NamiFaxScheduler] = None


def get_scheduler() -> NamiFaxScheduler:
    """Retrieve global singleton scheduler instance."""
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = NamiFaxScheduler()
    return _global_scheduler
