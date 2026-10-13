"""A job that is running (Run now, or started by the scheduler) shows as running with a Stop button; stopping it ends it at the next
safe point and the result says it was stopped. A job cannot be started twice at the same time."""

from __future__ import annotations

import os
import threading
import time
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from namifax.services import scheduler as sched_mod
from namifax.services import scheduler_config as cfg
from namifax.services.scheduler import NamiFaxScheduler


@pytest.fixture(autouse=True)
def _no_leftovers():
    yield
    sched_mod._RUNNING.clear()


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


# --- the control state ------------------------------------------------------------------------------------------------------

def test_a_running_job_is_known_while_it_runs_and_forgotten_after(dbsession):
    seen = {}

    def work(*args, **kwargs):
        seen["running"] = sched_mod.is_running("phonebook", dbsession)
        return 2

    with patch("namifax.services.scheduler.export_phonebook_count", side_effect=work):
        NamiFaxScheduler().run_job("phonebook", dbsession)
    assert seen["running"] is True and sched_mod.is_running("phonebook", dbsession) is False


def test_a_job_that_is_already_running_is_not_started_again(dbsession):
    handle = sched_mod.claim("phonebook", by="manual")
    assert handle is not None
    assert sched_mod.claim("phonebook", by="schedule") is None
    result = NamiFaxScheduler().run_job("phonebook", dbsession)
    assert result["ok"] is False and "already running" in result["summary"]
    sched_mod.release(handle)
    assert sched_mod.claim("phonebook", by="manual") is not None


def test_a_marker_left_by_a_dead_process_goes_stale(dbsession):
    cfg.mark_running(dbsession, "tmp", by="schedule", started="2000-01-01 00:00:00")
    assert sched_mod.is_running("tmp", dbsession) is False


def test_a_marker_from_another_process_counts_while_fresh(dbsession):
    cfg.mark_running(dbsession, "tmp", by="schedule")
    assert sched_mod.is_running("tmp", dbsession) is True


def test_stopping_a_job_in_this_process_sets_its_flag_at_once(dbsession):
    handle = sched_mod.claim("tmp", by="manual")
    sched_mod.request_stop("tmp", dbsession)
    assert handle.cancel.is_set() and cfg.cancel_requested(dbsession, "tmp") is True       # (and for another process to see)


def test_stopping_a_job_that_is_not_running_does_nothing(dbsession):
    sched_mod.request_stop("tmp", dbsession)
    assert cfg.cancel_requested(dbsession, "tmp") is False


# --- the jobs stop at a safe point -------------------------------------------------------------------------------------------

def test_a_stopped_inbox_job_reports_how_far_it_got(dbsession):
    def prune(days, should_stop=None):
        done = 0
        for _ in range(10):
            if should_stop and should_stop():
                break
            done += 1
            if done == 3:
                sched_mod.request_stop("inbox", dbsession)
        return done

    with patch("namifax.services.scheduler.ArchiveIn") as inbox:
        inbox.return_value.prune_inbox.side_effect = prune
        result = NamiFaxScheduler().run_job("inbox", dbsession, by="manual")
    assert result.get("stopped") is True and "stopped" in result["summary"].lower() and "3" in result["summary"]
    assert cfg.cancel_requested(dbsession, "inbox") is False                                # the request is used up
    assert cfg.last_run(dbsession, "inbox")["stopped"] is True


def test_a_stopped_phonebook_export_writes_nothing():
    from unittest.mock import MagicMock

    from namifax.cli import phb

    book = MagicMock()
    book.get_companies.return_value = [{"company": "A", "abook_id": 1}, {"company": "B", "abook_id": 2}]
    book.get_faxnums.return_value = [{"faxnumber": "1"}]
    with pytest.raises(sched_mod.JobStopped):
        phb.generate_phonebook_content(book, should_stop=lambda: True)


def test_the_temp_cleanup_stops_between_files(tmp_path):
    from namifax.cli.cron import run_cron

    for i in range(6):
        f = tmp_path / f"old{i}"
        f.write_text("x")
        os.utime(f, (1, 1))
    calls = {"n": 0}

    def stop():
        calls["n"] += 1
        return calls["n"] > 2

    run_cron(["cron", "-t", "1"], tmp_dir=str(tmp_path), should_stop=stop)
    assert 0 < len(list(tmp_path.iterdir())) < 6                       # some were removed, then it stopped


def test_the_retention_policy_stops_between_faxes(dbsession, tmp_path):
    from namifax.services.storage_lifecycle import StorageLifecyclePolicy, StorageLifecycleService

    svc = StorageLifecycleService(db=dbsession, archive_dir=str(tmp_path))
    with patch.object(StorageLifecycleService, "purge_local_tiffs", return_value={"purged_count": 0, "reclaimed_bytes": 0}) as tiffs:
        out = svc.run_lifecycle(StorageLifecyclePolicy(full_retention_days=30), should_stop=lambda: True)
    assert out["faxes_purged"] == 0 and tiffs.called


# --- the page ----------------------------------------------------------------------------------------------------------------

def _job(page, job):
    block = BeautifulSoup(page.text, "html.parser").find(attrs={"data-job-status": job})
    return block


def test_an_idle_job_has_run_now_and_no_stop(client):
    block = _job(client.get("/admin/scheduler"), "phonebook")
    assert block.find("button", string=lambda s: s and "Run now" in s) is not None
    assert block.find("button", string=lambda s: s and "Stop" in s) is None


def test_a_running_job_shows_stop_and_not_run_now(client):
    handle = sched_mod.claim("phonebook", by="manual")
    block = _job(client.get("/admin/scheduler"), "phonebook")
    assert block.find("button", string=lambda s: s and "Stop" in s) is not None
    assert block.find("button", string=lambda s: s and "Run now" in s) is None
    assert "running" in block.get_text().lower()
    sched_mod.release(handle)


def test_run_now_starts_the_job_and_the_same_page_shows_stop(client):
    release = threading.Event()

    def slow(*args, **kwargs):
        release.wait(5)
        return 1

    run = next(f for f in client.get("/admin/scheduler").forms.values() if f.fields.get("job") and f["job"].value == "phonebook")
    with patch("namifax.services.scheduler.export_phonebook_count", side_effect=slow), \
            patch("namifax.services.scheduler.cli_session"), patch("namifax.services.scheduler.cfg.running_marker", return_value=None):
        res = run.submit()
        block = _job(res, "phonebook")
        assert block.find("button", string=lambda s: s and "Stop" in s) is not None
        release.set()
        for _ in range(50):
            if not sched_mod.is_running("phonebook"):
                break
            time.sleep(0.1)


def test_the_stop_button_asks_the_job_to_stop(client, dbsession):
    handle = sched_mod.claim("inbox", by="manual")
    stop = next(f for f in client.get("/admin/scheduler").forms.values() if f.fields.get("action") and f["action"].value == "stop_job"
                and f["job"].value == "inbox")
    stop.submit()
    assert handle.cancel.is_set()


def test_the_job_status_can_be_fetched_without_reloading(client):
    handle = sched_mod.claim("tmp", by="manual")
    html = client.get("/admin/scheduler/jobs").text
    soup = BeautifulSoup(html, "html.parser")
    assert soup.find(attrs={"data-job-status": "tmp"}).find("button", string=lambda s: s and "Stop" in s) is not None
    assert soup.find(attrs={"data-job-status": "phonebook"}).find("button", string=lambda s: s and "Run now" in s) is not None
    sched_mod.release(handle)


def test_the_page_polls_the_jobs(client):
    assert b"data-job-status" in client.get("/static/js/scheduler.js").body


def test_a_stopped_result_is_shown_in_amber_not_as_a_failure(client, dbsession):
    cfg.record_run(dbsession, "inbox", True, "stopped after 3 fax(es)", stopped=True)
    block = _job(client.get("/admin/scheduler"), "inbox")
    assert "stopped after 3" in block.get_text() and "text-amber" in str(block)


# --- the phonebook summary counts real entries; schedules do not overlap across processes -------------------------------------------

def test_the_phonebook_export_reports_how_many_entries_it_wrote(tmp_path):
    from namifax.cli import phb

    class Book:
        def get_companies(self):
            return [{"company": "A", "abook_id": 1}, {"company": "B", "abook_id": 2}]

        def loadbycid(self, cid):
            pass

        def get_faxnums(self):
            return [{"faxnumber": "123"}]

    out = tmp_path / "pb"
    assert phb.export_phonebook_count(str(out), addressbook=Book()) == 2
    assert phb.export_phonebook(str(out), addressbook=Book()) == 0           # the exit code contract is unchanged


def test_the_phonebook_job_summary_uses_the_real_entry_count(dbsession, tmp_path):
    with patch("namifax.cli.phb.DEFAULT_PHONEBOOK_PATH", str(tmp_path / "pb")), \
            patch("namifax.services.scheduler.export_phonebook_count", return_value=3):
        result = NamiFaxScheduler().run_job("phonebook", dbsession)
    assert result["ok"] is True and "3 entries" in result["summary"]


def test_a_scheduled_run_yields_to_a_fresh_marker_of_another_process(dbsession):
    cfg.mark_running(dbsession, "phonebook", by="schedule")
    with patch("namifax.services.scheduler.export_phonebook_count") as work:
        result = NamiFaxScheduler().run_job("phonebook", dbsession)
    assert result["ok"] is False and result["stopped"] is False and "already running" in result["summary"]
    work.assert_not_called()
    assert sched_mod.running_handle("phonebook") is None                       # the local reservation was given back
    assert cfg.running_marker(dbsession, "phonebook") is not None              # the other process's marker is left alone


def test_a_stale_marker_does_not_block_and_the_marker_is_cleared_at_the_end(dbsession):
    cfg.mark_running(dbsession, "phonebook", by="schedule", started="2000-01-01 00:00:00")
    with patch("namifax.services.scheduler.export_phonebook_count", return_value=1):
        result = NamiFaxScheduler().run_job("phonebook", dbsession)
    assert result["ok"] is True
    assert cfg.running_marker(dbsession, "phonebook") is None
