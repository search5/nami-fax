"""The scheduled maintenance as an administrator sets it (Admin > Scheduler), kept in the SystemConfig table.

Four jobs: ``tmp`` (clean the temporary folder), ``inbox`` (move faxes older than N days out of the inbox into the archive),
``lifecycle`` (the retention policy saved on the Storage page) and ``phonebook`` (export the address book to HylaFAX).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional

from namifax.services.system_config import SystemConfigService

JOBS = ("tmp", "inbox", "lifecycle", "phonebook")
HEARTBEAT_KEY = "sched_heartbeat"
ALIVE_SECONDS = 180


@dataclass
class JobSettings:
    tmp_enabled: bool = True
    tmp_time: str = "00:00"
    tmp_days: int = 1
    inbox_enabled: bool = False                # moving faxes to the archive is an explicit choice
    inbox_time: str = "01:00"
    inbox_days: int = 30
    lifecycle_enabled: bool = True             # (runs only when a policy was saved on the Storage page)
    lifecycle_time: str = "00:00"
    phonebook_enabled: bool = True
    phonebook_minutes: int = 60


def clean_time(value: Any, default: str = "00:00") -> str:
    """``HH:MM`` (24 hours); a value that is not a time becomes ``default``."""
    found = re.fullmatch(r"\s*(\d{1,2}):(\d{1,2})\s*", str(value or ""))
    if not found:
        return default
    hour, minute = int(found.group(1)), int(found.group(2))
    return f"{hour:02d}:{minute:02d}" if hour < 24 and minute < 60 else default


def _number(value: Any, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(str(value).strip())))
    except (TypeError, ValueError):
        return default


def load(session: Any) -> JobSettings:
    store = SystemConfigService(session)
    base = JobSettings()
    flag = lambda key, default: store.get(f"sched_{key}", "1" if default else "0") == "1"      # noqa: E731
    return JobSettings(
        tmp_enabled=flag("tmp_enabled", base.tmp_enabled),
        tmp_time=clean_time(store.get("sched_tmp_time", base.tmp_time), base.tmp_time),
        tmp_days=_number(store.get("sched_tmp_days", base.tmp_days), base.tmp_days, 1, 3650),
        inbox_enabled=flag("inbox_enabled", base.inbox_enabled),
        inbox_time=clean_time(store.get("sched_inbox_time", base.inbox_time), base.inbox_time),
        inbox_days=_number(store.get("sched_inbox_days", base.inbox_days), base.inbox_days, 1, 3650),
        lifecycle_enabled=flag("lifecycle_enabled", base.lifecycle_enabled),
        lifecycle_time=clean_time(store.get("sched_lifecycle_time", base.lifecycle_time), base.lifecycle_time),
        phonebook_enabled=flag("phonebook_enabled", base.phonebook_enabled),
        phonebook_minutes=_number(store.get("sched_phonebook_minutes", base.phonebook_minutes), base.phonebook_minutes, 1, 10080),
    )


def save(session: Any, settings: JobSettings) -> None:
    store = SystemConfigService(session)
    for key, value in asdict(settings).items():
        store.set(f"sched_{key}", ("1" if value else "0") if isinstance(value, bool) else str(value))
    session.flush()


STALE_RUNNING_SECONDS = 6 * 3600          # a "running" marker older than this was left by a process that died


def mark_running(session: Any, job: str, by: str = "schedule", started: Optional[str] = None) -> None:
    """Say a job is running (so that another process can show it and ask it to stop)."""
    SystemConfigService(session).set(f"sched_running_{job}", json.dumps(
        {"by": by, "started": started or datetime.now().strftime("%Y-%m-%d %H:%M:%S")}))


def running_marker(session: Any, job: str) -> Optional[dict]:
    raw = SystemConfigService(session).get(f"sched_running_{job}", "")
    try:
        info = json.loads(raw) if raw else None
    except ValueError:
        return None
    if not info:
        return None
    try:
        age = (datetime.now() - datetime.strptime(info["started"], "%Y-%m-%d %H:%M:%S")).total_seconds()
    except (KeyError, ValueError):
        return None
    return info if age < STALE_RUNNING_SECONDS else None


def clear_running(session: Any, job: str) -> None:
    SystemConfigService(session).set(f"sched_running_{job}", "")


def request_cancel(session: Any, job: str) -> None:
    SystemConfigService(session).set(f"sched_cancel_{job}", "1")


def cancel_requested(session: Any, job: str) -> bool:
    return SystemConfigService(session).get(f"sched_cancel_{job}", "") == "1"


def clear_cancel(session: Any, job: str) -> None:
    SystemConfigService(session).set(f"sched_cancel_{job}", "")


def stopped(session: Any) -> bool:
    """Has an administrator stopped the scheduler? (It keeps running as a process so that it can hear the start, but runs nothing.)"""
    return SystemConfigService(session).get("sched_stopped", "0") == "1"


def set_stopped(session: Any, value: bool) -> None:
    SystemConfigService(session).set("sched_stopped", "1" if value else "0")


def signature(session: Any) -> str:
    """A string that changes when any scheduling setting does (the running scheduler compares it)."""
    return json.dumps({**asdict(load(session)), "stopped": stopped(session)}, sort_keys=True)


def record_run(session: Any, job: str, ok: bool, summary: str, stopped: bool = False) -> dict:
    result = {"ok": bool(ok), "summary": summary, "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "stopped": bool(stopped)}
    SystemConfigService(session).set(f"sched_last_{job}", json.dumps(result))
    return result


def last_run(session: Any, job: str) -> Optional[dict]:
    raw = SystemConfigService(session).get(f"sched_last_{job}", "")
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def beat(session: Any, state: str = "running") -> None:
    """A scheduler process is alive: it says so (and whether its APScheduler engine is ``running`` or ``stopped``)."""
    store = SystemConfigService(session)
    store.set(HEARTBEAT_KEY, datetime.now().isoformat(timespec="seconds"))
    store.set("sched_engine_state", state)


def engine_state(session: Any) -> str:
    return SystemConfigService(session).get("sched_engine_state", "running")


def heartbeat(session: Any) -> Optional[datetime]:
    raw = SystemConfigService(session).get(HEARTBEAT_KEY, "")
    try:
        return datetime.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def alive(session: Any) -> bool:
    seen = heartbeat(session)
    return bool(seen and (datetime.now() - seen).total_seconds() < ALIVE_SECONDS)
