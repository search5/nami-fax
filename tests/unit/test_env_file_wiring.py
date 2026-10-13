"""/etc/namifax.env must reach every NamiFAX process: systemd services, cron jobs and the HylaFAX hook scripts."""

from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = "/etc/namifax.env"
HOOKS = ["dynconf", "faxcover", "faxrcvd", "notify"]
SERVICES = ["namifax.service"]
FIELD = r"[\d*/,-]+"


@pytest.mark.parametrize("name", SERVICES)
def test_service_reads_the_env_file_and_starts_without_it(name):
    text = (ROOT / "systemd" / name).read_text()
    assert f"EnvironmentFile=-{ENV_FILE}" in text.splitlines()


def _cron_commands():
    """(line, command) for every cron entry, including the commented-out examples."""
    out = []
    pattern = rf"^#?\s*{FIELD}\s+{FIELD}\s+{FIELD}\s+{FIELD}\s+{FIELD}\s+uucp\s+(.*)$"
    for line in (ROOT / "deploy" / "cron.d" / "namifax").read_text().splitlines():
        m = re.match(pattern, line)
        if m:
            out.append((line, m.group(1)))
    return out


def test_cron_has_the_four_entries():
    assert len(_cron_commands()) == 4


@pytest.mark.parametrize("idx", range(4))
def test_cron_command_reads_the_env_file_first(idx):
    _line, cmd = _cron_commands()[idx]
    assert cmd.startswith("sh -c '") and cmd.endswith("'")
    inner = cmd[len("sh -c '"):-1]
    assert inner.index("set -a") < inner.index(f". {ENV_FILE}") < inner.index("set +a") < inner.index("namifax cron")
    assert "'" not in inner


def _fake_install(tmp_path, binary):
    """A fake NamiFAX install whose `binary` prints the variables we care about; returns (home, env_file)."""
    home = tmp_path / "home"
    (home / ".venv" / "bin").mkdir(parents=True)
    exe = home / ".venv" / "bin" / binary
    exe.write_text('#!/bin/sh\necho "DB=$DATABASE_URL SECRET=$NAMIFAX_SECRET_KEY ARGS=$*"\n')
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    env_file = tmp_path / "namifax.env"
    # the documented format: plain KEY=value, no quotes, no export
    env_file.write_text("DATABASE_URL=mysql+pymysql://u:pw@localhost/db\nNAMIFAX_SECRET_KEY=abc123\n")
    return home, env_file


def _clean_env(**extra):
    env = {"PATH": os.environ["PATH"]}
    env.update(extra)
    return env


@pytest.mark.parametrize("hook", HOOKS)
def test_hook_script_passes_env_file_variables_to_the_program(tmp_path, hook):
    home, env_file = _fake_install(tmp_path, f"namifax-{hook}")
    script = tmp_path / hook
    script.write_text((ROOT / "deploy" / "hylafax" / "bin" / hook).read_text().replace(ENV_FILE, str(env_file)))
    res = subprocess.run(["sh", str(script), "a", "b"], capture_output=True, text=True,
                         env=_clean_env(NAMIFAX_HOME=str(home)))
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "DB=mysql+pymysql://u:pw@localhost/db SECRET=abc123 ARGS=a b"


def test_hook_script_still_runs_without_the_env_file(tmp_path):
    home, _env_file = _fake_install(tmp_path, "namifax-notify")
    script = tmp_path / "notify"
    text = (ROOT / "deploy" / "hylafax" / "bin" / "notify").read_text()
    script.write_text(text.replace(ENV_FILE, str(tmp_path / "missing.env")))
    res = subprocess.run(["sh", str(script)], capture_output=True, text=True, env=_clean_env(NAMIFAX_HOME=str(home)))
    assert res.returncode == 0 and res.stdout.strip() == "DB= SECRET= ARGS="


@pytest.mark.parametrize("idx", range(4))
def test_cron_command_passes_env_file_variables_to_namifax(tmp_path, idx):
    home, env_file = _fake_install(tmp_path, "namifax")
    _line, cmd = _cron_commands()[idx]
    inner = cmd[len("sh -c '"):-1].replace(ENV_FILE, str(env_file)).replace("/opt/namifax", str(home))
    res = subprocess.run(["sh", "-c", inner], capture_output=True, text=True, env=_clean_env())
    assert res.returncode == 0, res.stderr
    assert res.stdout.startswith("DB=mysql+pymysql://u:pw@localhost/db SECRET=abc123 ARGS=cron")


def test_install_guide_sample_uses_the_plain_key_value_format():
    """The sample must be readable by both systemd (EnvironmentFile) and `sh` (set -a; .)."""
    doc = (ROOT / "docs" / "ko" / "install" / "hylafax.md").read_text()
    block = re.search(r"## 0\. .*?```\n(.*?)```", doc, re.S).group(1)
    lines = [ln.split("#", 1)[0].strip() for ln in block.splitlines()]
    lines = [ln for ln in lines if ln]
    assert lines
    for line in lines:
        assert re.fullmatch(r"[A-Z_][A-Z0-9_]*=([^\s'\"]*|\"[^$`\\\"]*\")", line), line


def test_a_quoted_value_with_special_characters_survives_the_shell_and_the_cron_line(tmp_path):
    """DATABASE_URL=...&x=1 must be quoted in the env file: unquoted, `sh` would cut it at the & (the guide says so)."""
    home, env_file = _fake_install(tmp_path, "namifax-notify")
    env_file.write_text('DATABASE_URL="mysql+pymysql://u:pw@localhost/db?charset=utf8mb4&x=1 y;z"\nNAMIFAX_SECRET_KEY=abc123\n')
    script = tmp_path / "notify"
    script.write_text((ROOT / "deploy" / "hylafax" / "bin" / "notify").read_text().replace(ENV_FILE, str(env_file)))
    res = subprocess.run(["sh", str(script)], capture_output=True, text=True, env=_clean_env(NAMIFAX_HOME=str(home)))
    assert res.stdout.strip() == "DB=mysql+pymysql://u:pw@localhost/db?charset=utf8mb4&x=1 y;z SECRET=abc123 ARGS="
