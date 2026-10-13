"""The scheduler runs inside the web process (``namifax serve``); there is no separate scheduler service any more.

A second scheduler process on the same database could start the same job at the same moment (the "running" marker is read and then
written, not claimed in one step), so the separate ``namifax scheduler`` command, its systemd unit and its script entry were removed.
"""

from __future__ import annotations

import importlib
import inspect
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_the_scheduler_command_is_gone(capsys, monkeypatch):
    from namifax.services import scheduler

    def _never(self, *args, **kwargs):                  # before the removal the command started a scheduler and waited for ever
        raise AssertionError("the scheduler command must not start a scheduler")

    monkeypatch.setattr(scheduler.NamiFaxScheduler, "start", _never)
    app_main = importlib.import_module("namifax.main")
    assert app_main.main(["scheduler"]) != 0
    assert "Unknown command: scheduler" in capsys.readouterr().out


def test_the_usage_does_not_list_it(capsys):
    app_main = importlib.import_module("namifax.main")
    app_main.main([])
    assert not any(line.strip().startswith("scheduler ") for line in capsys.readouterr().out.splitlines())


def test_there_is_no_script_entry_for_it():
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
    assert "namifax-scheduler" not in scripts


def test_there_is_no_systemd_unit_for_it():
    assert not (ROOT / "systemd" / "namifax-scheduler.service").exists()
    assert (ROOT / "systemd" / "namifax.service").exists()


def test_the_standalone_runner_and_the_blocking_start_are_gone():
    from namifax.services import scheduler

    app_main = importlib.import_module("namifax.main")
    assert not hasattr(scheduler, "run_scheduler_standalone")
    assert not hasattr(app_main, "scheduler_main") and not hasattr(app_main, "run_scheduler_standalone")
    assert "blocking" not in inspect.signature(scheduler.NamiFaxScheduler.start).parameters


def test_the_web_service_still_starts_the_built_in_scheduler():
    source = (ROOT / "src" / "namifax" / "main.py").read_text(encoding="utf-8")
    assert 'os.environ.get("NAMIFAX_ENABLE_SCHEDULER", "1")' in source and "scheduler.start()" in source
