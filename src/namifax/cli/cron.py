#!/usr/bin/env python3
"""AvantFAX modern CLI replacement for includes/avantfaxcron.php.

Handles daily maintenance tasks including temporary directory cleanup and fax retention pruning.
"""

from __future__ import annotations

import contextlib
import getopt
import os
import shutil
import sys
import time
from typing import Any, Sequence

# Ensure src directory is on sys.path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from namifax.db.provider import cli_session
from namifax.services.archive_base import FaxPDFArchive
from namifax.services.archive_in import ArchiveIn

USAGE = """usage: avantfaxcron.php [-i num-days] [-d num-days] -t num-days
options:
 -i num-days\tprune Inbox of faxes older than number of days
 -d num-days\tdelete faxes from Inbox/Archive that are older than number of days
 -t num-days\tclean AvantFAX temporary directory of files older than number of days
 -p num-days\tdelete original TIFF files that are older than number of days when a PDF exists
 -s\t\trun the storage lifecycle policy saved on the admin Storage page (nothing runs unless one was saved)
"""

DEFAULT_TMPDIR = os.environ.get("AVANTFAX_TMPDIR", "/tmp/avantfax/")


def deltree(path: str) -> None:
    """Recursively delete directory tree or single file."""
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def run_cron(
    argv: Sequence[str] | None = None,
    archive_in: ArchiveIn | None = None,
    archive_base: FaxPDFArchive | None = None,
    tmp_dir: str | None = None,
    *,
    db: Any = None,
    should_stop=None,
) -> int:
    """Execute cron tasks based on command line options.

    The database is opened lazily, only when a task that needs it runs.
    """
    args = list(argv[1:]) if argv is not None else list(sys.argv[1:])
    stack = contextlib.ExitStack()
    with stack:
        return _run_cron(args, stack, db, archive_in, archive_base, tmp_dir, should_stop)


def _run_cron(
    args: list[str],
    stack: contextlib.ExitStack,
    db: Any,
    archive_in: ArchiveIn | None,
    archive_base: FaxPDFArchive | None,
    tmp_dir: str | None,
    should_stop=None,
) -> int:
    def get_db() -> Any:
        nonlocal db
        if db is None:
            db = stack.enter_context(cli_session(ensure_schema=True))
        return db

    try:
        opts, _ = getopt.getopt(args, "i:t:d:p:s")
    except getopt.GetoptError:
        print(USAGE, end="")
        return 0

    opt_dict = dict(opts)

    # -t option is mandatory
    if "-t" not in opt_dict:
        print(USAGE, end="")
        return 0

    try:
        tmpdays = int(opt_dict["-t"])
    except ValueError:
        print(USAGE, end="")
        return 0

    recdays = int(opt_dict["-i"]) if "-i" in opt_dict else None
    deldays = int(opt_dict["-d"]) if "-d" in opt_dict else None

    # 1. Prune old faxes from Inbox
    if recdays is not None:
        inbox_svc = archive_in or ArchiveIn(db=get_db())
        inbox_svc.prune_inbox(recdays)

    # 2. Delete faxes from Inbox/Archive
    if deldays is not None:
        arch_svc = archive_base or FaxPDFArchive(db=get_db())
        arch_svc.prune_archive(deldays)

    # 3. Clean temporary directory
    target_tmp = tmp_dir or DEFAULT_TMPDIR
    if os.path.exists(target_tmp):
        now = time.time()
        for item in os.listdir(target_tmp):
            if should_stop and should_stop():
                return 0
            if item in (".", "..", "index.html"):
                continue
            full_p = os.path.join(target_tmp, item)
            try:
                mtime = os.path.getmtime(full_p)
                diff_days = round((now - mtime) / 86400)
                if diff_days >= tmpdays:
                    deltree(full_p)
            except OSError:
                pass

    # 4. Storage Lifecycle TIFF purge
    if "-p" in opt_dict:
        try:
            purgelifedays = int(opt_dict["-p"])
            from namifax.services.storage_lifecycle import StorageLifecycleService
            lifecycle = StorageLifecycleService(db=get_db())
            lifecycle.purge_local_tiffs(days_old=purgelifedays)
        except ValueError:
            pass

    # 5. The saved storage lifecycle policy (retention and TIFF purge, local and remote)
    if "-s" in opt_dict:
        from namifax.services.storage_lifecycle import StorageLifecycleService

        StorageLifecycleService(db=get_db()).run_saved_policy()

    return 0


def main() -> None:
    sys.exit(run_cron(sys.argv))


if __name__ == "__main__":
    main()
