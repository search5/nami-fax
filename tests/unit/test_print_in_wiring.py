"""`namifax print-in` is the command the docs and the CUPS backend call; it must exist and reach the print-to-fax code."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from unittest.mock import patch

from namifax.main import USAGE, main

ROOT = Path(__file__).resolve().parents[2]


def test_the_command_is_listed_and_dispatched():
    assert "print-in" in USAGE
    with patch("namifax.cli.print_in.main", return_value=3) as target:
        assert main(["print-in", "7", "alice", "Doc", "1", ""]) == 3
    target.assert_called_once()
    assert target.call_args.args[0][1:] == ["7", "alice", "Doc", "1", ""]


def test_the_cups_backend_script_passes_the_job_to_the_command(tmp_path):
    script = ROOT / "deploy" / "cups" / "namifax-fax"
    assert script.exists() and os.access(script, os.R_OK)
    text = script.read_text()
    assert "/etc/namifax.env" in text and "set -a" in text and "print-in" in text
    # without arguments a CUPS backend lists itself ("device-class scheme "make-and-model" "info"") and exits 0
    home = tmp_path / "home"
    (home / ".venv" / "bin").mkdir(parents=True)
    exe = home / ".venv" / "bin" / "namifax"
    exe.write_text('#!/bin/sh\necho "ARGS=$*"\n')
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    listed = subprocess.run(["sh", str(script)], capture_output=True, text=True, env={"PATH": os.environ["PATH"], "NAMIFAX_HOME": str(home)})
    assert listed.returncode == 0 and listed.stdout.startswith("direct namifax-fax")
    done = subprocess.run(["sh", str(script), "12", "alice", "Doc", "1", "opts", "/tmp/x.ps"], capture_output=True, text=True,
                          env={"PATH": os.environ["PATH"], "NAMIFAX_HOME": str(home)})
    assert done.stdout.strip() == "ARGS=print-in 12 alice Doc 1 opts /tmp/x.ps"
