"""Storage lifecycle against the legacy table layout (retention by archstamp, files by faxpath).

The first version looked at a column (``lastmod``) that the legacy FaxArchive does not have and that nothing
ever wrote, searched for directories named ``fax<fid>`` although faxrcvd stores faxes under
``<archive>/<day>/<number>/<hylafax id>``, and was never run by the scheduler.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from namifax.models import FaxArchive
from namifax.services.storage_lifecycle import StorageLifecyclePolicy, StorageLifecycleService


def _days_ago(n):
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d %H:%M:%S")


def _fax(session, tmp_path, name, age_days, inbox=0, files=("fax.tif", "fax.pdf", "thumb.png")):
    """A fax laid out like faxrcvd does: <archive>/<day>/<number>/<hylafax id>/ with absolute faxpath."""
    path = tmp_path / "archive" / "2025-01-01" / "5551234" / name
    path.mkdir(parents=True)
    for f in files:
        (path / f).write_bytes(b"%PDF-1.4 x" if f.endswith("pdf") else b"data")
    row = FaxArchive(faxpath=str(path), pages=1, inbox=inbox, archstamp=_days_ago(age_days))
    session.add(row)
    session.flush()
    return row.fid, path


@pytest.fixture
def archive_dir(tmp_path):
    (tmp_path / "archive").mkdir()
    return str(tmp_path / "archive")


@pytest.fixture
def svc(dbsession, archive_dir):
    dbsession.execute(sa.delete(FaxArchive))
    remote = MagicMock()
    return StorageLifecycleService(db=dbsession, storage_provider=remote, archive_dir=archive_dir)


def _exists(session, fid):
    return session.get(FaxArchive, fid) is not None


def test_expired_faxes_are_removed_with_their_files_by_archstamp(svc, dbsession, tmp_path):
    old, old_dir = _fax(dbsession, tmp_path, "100", 400)
    old_inbox, inbox_dir = _fax(dbsession, tmp_path, "101", 500, inbox=1)
    recent, recent_dir = _fax(dbsession, tmp_path, "102", 10)

    res = svc.purge_expired_faxes(retention_days=365)

    assert res == {"purged_faxes_count": 2}
    assert not _exists(dbsession, old) and not _exists(dbsession, old_inbox) and _exists(dbsession, recent)
    assert not old_dir.exists() and not inbox_dir.exists()                  # found through faxpath, not "fax<fid>"
    assert recent_dir.exists() and (recent_dir / "fax.pdf").exists()
    assert sorted(c.args[0] for c in svc.storage_provider.delete_fax.call_args_list) == sorted([old, old_inbox])


def test_a_remote_failure_does_not_stop_the_purge(svc, dbsession, tmp_path):
    fid, path = _fax(dbsession, tmp_path, "100", 400)
    svc.storage_provider.delete_fax.side_effect = RuntimeError("bucket unreachable")
    assert svc.purge_expired_faxes(365) == {"purged_faxes_count": 1}
    assert not _exists(dbsession, fid) and not path.exists()


def test_zero_retention_keeps_everything_forever(svc, dbsession, tmp_path):
    fid, path = _fax(dbsession, tmp_path, "100", 4000)
    assert svc.purge_expired_faxes(0) == {"purged_faxes_count": 0}
    assert _exists(dbsession, fid) and path.exists()


def test_files_outside_the_archive_are_never_touched(svc, dbsession, tmp_path):
    outside = tmp_path / "precious"
    outside.mkdir()
    (outside / "keep.txt").write_text("x")
    row = FaxArchive(faxpath=str(outside), pages=1, inbox=0, archstamp=_days_ago(900))
    dbsession.add(row)
    dbsession.flush()
    assert svc.purge_expired_faxes(365) == {"purged_faxes_count": 1}       # the record goes ...
    assert (outside / "keep.txt").exists()                                    # ... a stray directory does not


def test_run_lifecycle_purges_tiffs_then_faxes_and_honours_remote_sync(svc, dbsession, tmp_path):
    old_tiff_fax, old_dir = _fax(dbsession, tmp_path, "100", 20)
    os.utime(old_dir / "fax.tif", (time.time() - 20 * 86400,) * 2)
    expired, _ = _fax(dbsession, tmp_path, "101", 400)
    summary = svc.run_lifecycle(StorageLifecyclePolicy(purge_tiff_after_days=7, full_retention_days=365,
                                                       remote_sync_delete=False))
    assert summary["tiffs_purged"] == 1 and summary["faxes_purged"] == 1
    assert not (old_dir / "fax.tif").exists() and (old_dir / "fax.pdf").exists() and _exists(dbsession, old_tiff_fax)
    svc.storage_provider.delete_fax.assert_not_called()                        # remote_sync_delete is off


# --- the saved policy actually runs ---------------------------------------------------------------------------

def test_the_saved_policy_is_run_only_when_an_administrator_saved_one(svc, dbsession, tmp_path):
    from namifax.services.system_config import SystemConfigService

    fid, _ = _fax(dbsession, tmp_path, "100", 4000)
    assert svc.run_saved_policy() is None                                      # defaults alone never delete anything
    assert _exists(dbsession, fid)

    cfg = SystemConfigService(dbsession)
    cfg.set("storage_purge_tiff_days", "7")
    cfg.set("storage_retention_days", "365")
    cfg.set("storage_remote_sync_delete", "1")
    summary = svc.run_saved_policy()
    assert summary["faxes_purged"] == 1 and not _exists(dbsession, fid)


def test_cron_runs_the_saved_policy_with_the_s_option(dbsession, archive_dir, tmp_path, monkeypatch):
    from contextlib import contextmanager

    from namifax.cli import cron
    from namifax.services.system_config import SystemConfigService

    dbsession.execute(sa.delete(FaxArchive))
    fid, _ = _fax(dbsession, tmp_path, "100", 4000)
    SystemConfigService(dbsession).set("storage_retention_days", "365")
    monkeypatch.setenv("NAMIFAX_ARCHIVE_DIR", archive_dir)

    @contextmanager
    def fake_session(*a, **k):
        yield dbsession

    monkeypatch.setattr(cron, "cli_session", fake_session)
    assert cron.run_cron(["cron", "-t", "1", "-s"], tmp_dir=str(tmp_path / "none")) == 0
    assert not _exists(dbsession, fid)


def test_cron_prunes_with_the_session_and_removes_files(dbsession, tmp_path, monkeypatch):
    from contextlib import contextmanager

    from namifax.cli import cron

    dbsession.execute(sa.delete(FaxArchive))
    fid, path = _fax(dbsession, tmp_path, "100", 40)

    @contextmanager
    def fake_session(*a, **k):
        yield dbsession

    monkeypatch.setattr(cron, "cli_session", fake_session)
    assert cron.run_cron(["cron", "-t", "1", "-d", "30"], tmp_dir=str(tmp_path / "none")) == 0
    assert not _exists(dbsession, fid) and not path.exists()


def test_the_scheduler_runs_the_saved_policy_every_day(dbsession):
    from apscheduler.triggers.cron import CronTrigger

    from namifax.services.scheduler import NamiFaxScheduler

    sched = NamiFaxScheduler()
    sched.start()
    try:
        sched.apply_config(dbsession)
        job = sched._scheduler.get_job("lifecycle")
        assert job is not None and isinstance(job.trigger, CronTrigger)           # once a day, at the time set on the Scheduler page
    finally:
        sched.stop()


# --- real servers --------------------------------------------------------------------------------------------

@pytest.mark.serverdb
def test_server_database(monkeypatch, server_db_url, alembic_cfg, tmp_path):
    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as s:
            fid, path = _fax(s, tmp_path, "100", 400)
            keep, keep_dir = _fax(s, tmp_path, "101", 5)
            svc = StorageLifecycleService(db=s, archive_dir=str(tmp_path / "archive"))
            assert svc.purge_expired_faxes(365) == {"purged_faxes_count": 1}
            s.commit()
        with Session(engine) as s:
            assert [r for r in s.execute(sa.select(FaxArchive.fid)).scalars()] == [keep]
        assert not path.exists() and keep_dir.exists()
    finally:
        engine.dispose()
