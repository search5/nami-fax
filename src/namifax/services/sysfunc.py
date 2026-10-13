"""What the System Functions page does (the original admin/system_func.php): reboot, halt, archive and database downloads."""

from __future__ import annotations

import gzip
import os
import shlex
import sqlite3
import subprocess
import tarfile
import tempfile
from typing import Optional, Tuple

from sqlalchemy.engine import URL

from namifax.common import settings


def _pid_of(process: str) -> Optional[str]:
    """The process id of a running program (``pgrep -x``), None when it is not running, ``"unknown"`` when it cannot be asked."""
    try:
        found = subprocess.run(["pgrep", "-x", process], capture_output=True, text=True, timeout=5)
    except Exception:                                          # no pgrep, no permission, ...: the page must still open
        return "unknown"
    if found.returncode != 0:
        return None
    return (found.stdout.split() or [None])[0]


def daemon_status() -> dict:
    """What the Daemon Service Control panel shows: the HylaFAX queue daemon, its server, and this web worker."""
    return {"faxq": _pid_of("faxq"), "hfaxd": _pid_of("hfaxd"), "web": str(os.getpid())}


def reboot_command() -> list[str]:
    return shlex.split(os.environ.get("NAMIFAX_REBOOT_CMD") or "sudo /sbin/reboot")


def shutdown_command() -> list[str]:
    return shlex.split(os.environ.get("NAMIFAX_SHUTDOWN_CMD") or "sudo /sbin/halt")


def archive_folders() -> list[str]:
    """The received and the sent fax archive folders that exist (the original's $ARCHIVE and $ARCHIVE_SENT)."""
    received = settings.archive_dir()
    sent = os.environ.get("AVANTFAX_ARCHIVE_SENT") or settings.sent_dir()
    return [p for p in (received, sent) if p and os.path.isdir(p)]


def write_archive(path: str) -> int:
    """Pack the archive folders into a gzipped tarball; returns how many folders were packed."""
    folders = archive_folders()
    with tarfile.open(path, "w:gz") as tar:
        for folder in folders:
            tar.add(folder, arcname=os.path.basename(folder.rstrip("/")) or "archive")
    return len(folders)


def is_sqlite(url: URL) -> bool:
    return url.get_backend_name() == "sqlite"


def dump_command(url: URL) -> Tuple[list[str], dict]:
    """The dump program and its environment for a server database; the password goes in the environment, not in the arguments."""
    env = dict(os.environ)
    backend = url.get_backend_name()
    if backend in ("mysql", "mariadb"):
        argv = ["mysqldump", f"--user={url.username or ''}"]
        if url.host:
            argv.append(f"--host={url.host}")
        if url.port:
            argv.append(f"--port={url.port}")
        if url.password:
            env["MYSQL_PWD"] = url.password
        return [*argv, url.database or ""], env
    if backend == "postgresql":
        argv = ["pg_dump", f"--username={url.username or ''}"]
        if url.host:
            argv.append(f"--host={url.host}")
        if url.port:
            argv.append(f"--port={url.port}")
        if url.password:
            env["PGPASSWORD"] = url.password
        return [*argv, url.database or ""], env
    raise ValueError(f"No dump program for {backend}")


def write_sqlite_dump(db_path: str, target: str) -> None:
    connection = sqlite3.connect(db_path)
    try:
        with gzip.open(target, "wt", encoding="utf-8") as out:
            for line in connection.iterdump():
                out.write(line + "\n")
    finally:
        connection.close()
