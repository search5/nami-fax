"""Admin > System Functions: reboot, shut down, download the fax archive, download a database dump (the original system_func.php)."""

from __future__ import annotations

import gzip
import io
import os
import tarfile
from unittest.mock import patch

import pytest
from sqlalchemy.engine import make_url

from namifax.services.sysfunc import dump_command


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    # (looking at the page asks the process list; keep that out of the tests that watch subprocess.Popen)
    with patch("namifax.services.sysfunc.daemon_status", return_value={"faxq": None, "hfaxd": None, "web": "1"}):
        yield testapp


def _press(client, button):
    form = next(f for f in client.get("/admin/system_func").forms.values() if button in f.fields)
    return form.submit(button)


@pytest.mark.parametrize("button,default", [("reboot", ["sudo", "/sbin/reboot"]), ("shutdown", ["sudo", "/sbin/halt"])])
def test_reboot_and_shutdown_run_the_original_commands(client, button, default):
    with patch("subprocess.Popen") as popen:
        res = _press(client, button)
    popen.assert_called_once()
    assert popen.call_args.args[0] == default and res.status_int == 200
    assert "wait" in res.text.lower()


def test_the_commands_can_be_changed(client, monkeypatch):
    monkeypatch.setenv("NAMIFAX_REBOOT_CMD", "sudo /usr/sbin/shutdown -r now")
    with patch("subprocess.Popen") as popen:
        _press(client, "reboot")
    assert popen.call_args.args[0] == ["sudo", "/usr/sbin/shutdown", "-r", "now"]


def test_nothing_is_run_by_just_looking_at_the_page(client):
    with patch("subprocess.Popen") as popen:
        client.get("/admin/system_func")
    popen.assert_not_called()


def test_the_archive_download_is_a_tarball_of_the_received_and_sent_folders(client, tmp_path, monkeypatch):
    (tmp_path / "recv" / "2026").mkdir(parents=True)
    (tmp_path / "recv" / "2026" / "fax.pdf").write_bytes(b"%PDF received")
    (tmp_path / "sent").mkdir()
    (tmp_path / "sent" / "out.pdf").write_bytes(b"%PDF sent")
    monkeypatch.setenv("AVANTFAX_ARCHIVE", str(tmp_path / "recv"))
    monkeypatch.setenv("ARCHIVE_SENT", str(tmp_path / "sent"))
    res = _press(client, "download_ar")
    assert res.content_type in ("application/gzip", "application/x-gzip") and "avantfax-archive-" in res.headers["Content-Disposition"]
    names = tarfile.open(fileobj=io.BytesIO(res.body), mode="r:gz").getnames()
    assert any(n.endswith("fax.pdf") for n in names) and any(n.endswith("out.pdf") for n in names)


@pytest.mark.skipif(bool(os.environ.get("NAMIFAX_SUITE_DB")), reason="a SQLite dump; on a server the real dump tool would wait for the test's open transaction")
def test_the_database_dump_of_a_sqlite_database_is_gzipped_sql(client):
    res = _press(client, "download_db")
    assert "avantfax-schema-" in res.headers["Content-Disposition"] and res.headers["Content-Disposition"].endswith('.sql.gz"')
    sql = gzip.decompress(res.body).decode()
    assert "CREATE TABLE" in sql and "UserAccount" in sql


def test_a_mysql_dump_asks_mysqldump_without_the_password_on_the_command_line():
    argv, env = dump_command(make_url("mysql+pymysql://fax:s3cret@db.corp.test:3307/avantfax"))
    assert argv[0] == "mysqldump" and "--user=fax" in argv and "--host=db.corp.test" in argv and "--port=3307" in argv
    assert argv[-1] == "avantfax" and not any("s3cret" in a for a in argv) and env["MYSQL_PWD"] == "s3cret"


def test_a_postgresql_dump_asks_pg_dump_without_the_password_on_the_command_line():
    argv, env = dump_command(make_url("postgresql+psycopg://fax:s3cret@db.corp.test:5433/avantfax"))
    assert argv[0] == "pg_dump" and "--username=fax" in argv and "--host=db.corp.test" in argv and "--port=5433" in argv
    assert argv[-1] == "avantfax" and not any("s3cret" in a for a in argv) and env["PGPASSWORD"] == "s3cret"


def test_a_failing_dump_is_reported_instead_of_sent_empty(client, monkeypatch):
    import subprocess

    class Boom:
        def __init__(self, *a, **kw): raise FileNotFoundError("mysqldump")
    monkeypatch.setattr("namifax.services.sysfunc.is_sqlite", lambda url: False)
    monkeypatch.setattr(subprocess, "Popen", Boom)
    res = _press(client, "download_db")
    assert res.status_int == 200 and "text/html" in res.content_type and "could not" in res.text.lower()


# --- the daemon panel shows what is really running, not fixed text ------------------------------------------------------------

def test_daemon_status_reads_the_process_list():
    from namifax.services import sysfunc

    def fake_run(argv, **kwargs):
        class R:
            returncode = 0 if argv[-1] == "faxq" else 1
            stdout = "4242\n" if argv[-1] == "faxq" else ""
        return R()

    with patch("namifax.services.sysfunc.subprocess.run", side_effect=fake_run):
        status = sysfunc.daemon_status()
    assert status["faxq"] == "4242" and status["hfaxd"] is None and status["web"] == str(os.getpid())


def test_daemon_status_says_unknown_when_pgrep_is_missing():
    from namifax.services import sysfunc

    with patch("namifax.services.sysfunc.subprocess.run", side_effect=FileNotFoundError):
        status = sysfunc.daemon_status()
    assert status["faxq"] == "unknown" and status["hfaxd"] == "unknown" and status["web"] == str(os.getpid())


def test_the_page_shows_real_status_and_no_invented_numbers(client):
    with patch("namifax.services.sysfunc.daemon_status", return_value={"faxq": "4242", "hfaxd": None, "web": "77"}):
        text = client.get("/admin/system_func").text
    assert "pid 4242" in text and "pid 77" in text and "NOT RUNNING" in text.upper()
    assert "pid 1024" not in text and "pid 2048" not in text and "4559" not in text
