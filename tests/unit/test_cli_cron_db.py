"""Spec 48 loop C3: cron CLI opens the database lazily and only when a task needs it."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from namifax.cli import cron as mod


def _run(argv, tmp_path, **kwargs):
    classes = {n: MagicMock(name=n) for n in ("ArchiveIn", "FaxPDFArchive")}
    lifecycle = MagicMock(name="StorageLifecycleService")
    with patch.multiple(mod, **classes), \
            patch("namifax.services.storage_lifecycle.StorageLifecycleService", lifecycle):
        code = mod.run_cron(["cron.py", *argv], tmp_dir=str(tmp_path), **kwargs)
    return code, classes, lifecycle


def test_injected_db_reaches_every_service(tmp_path, monkeypatch):
    db = object()
    code, classes, lifecycle = _run(["-t", "30", "-i", "7", "-d", "9", "-p", "3"], tmp_path, db=db)
    assert code == 0
    for cls in (*classes.values(), lifecycle):
        assert cls.call_args_list, cls._mock_name
        for call in cls.call_args_list:
            assert call.kwargs.get("db") is db, cls._mock_name


def test_tmp_cleanup_only_does_not_open_a_database(tmp_path):
    with patch.object(mod, "cli_session", side_effect=AssertionError("must not open DB")):
        code, classes, lifecycle = _run(["-t", "30"], tmp_path)
    assert code == 0
    assert not classes["ArchiveIn"].called and not lifecycle.called


def test_database_is_opened_once_and_shared(tmp_path):
    opened, calls = object(), []

    @contextmanager
    def fake_cli_db(*a, **k):
        calls.append(1)
        yield opened

    with patch.object(mod, "cli_session", fake_cli_db):
        code, classes, lifecycle = _run(["-t", "30", "-i", "7", "-d", "9", "-p", "3"], tmp_path)
    assert code == 0 and calls == [1]
    assert classes["ArchiveIn"].call_args.kwargs.get("db") is opened
    assert classes["FaxPDFArchive"].call_args.kwargs.get("db") is opened
    assert lifecycle.call_args.kwargs.get("db") is opened


def test_injected_services_do_not_open_a_database(tmp_path):
    arc_in, arc_base = MagicMock(), MagicMock()
    with patch.object(mod, "cli_session", side_effect=AssertionError("must not open DB")):
        code = mod.run_cron(["cron.py", "-t", "30", "-i", "7", "-d", "9"], archive_in=arc_in,
                            archive_base=arc_base, tmp_dir=str(tmp_path))
    assert code == 0
    arc_in.prune_inbox.assert_called_once_with(7)
    arc_base.prune_archive.assert_called_once_with(9)
