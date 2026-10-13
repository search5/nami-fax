"""Legacy parity: avantfaxlog() records events in the SysLog table (and keeps writing to the OS syslog)."""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session


def _rows(session, **filters):
    from namifax.services.syslog import SysLogService

    return SysLogService(session).search(**filters)


# --- SysLogService.add ---------------------------------------------------------------------

def test_add_stores_the_text_with_the_current_time(dbsession):
    from namifax.services.syslog import SysLogService

    svc = SysLogService(dbsession)
    svc.add("faxrcvd> Inserted fax from Acme")
    row = svc.search(kw="inserted fax")[0]
    assert row["logtext"] == "faxrcvd> Inserted fax from Acme"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", row["logdate"])


def test_add_accepts_an_explicit_date_and_keeps_quotes_backslashes_and_unicode(dbsession):
    from namifax.services.syslog import SysLogService

    tricky = "user 'o\\'brien' 한글 \"q\""
    svc = SysLogService(dbsession)
    svc.add(tricky, logdate="2026-10-01 09:08:07")
    assert svc.search(year="2026", month="10", day="1")[0] == {"logdate": "2026-10-01 09:08:07", "logtext": tricky}


def test_newest_entries_come_first(dbsession):
    from namifax.services.syslog import SysLogService

    svc = SysLogService(dbsession)
    svc.add("first", logdate="2026-10-01 10:00:00")
    svc.add("second", logdate="2026-10-01 10:00:00")
    assert [r["logtext"] for r in svc.search(year="2026", month="10", day="01")] == ["second", "first"]


def test_add_without_a_session_fails_loudly():
    from namifax.services.syslog import SysLogService

    with pytest.raises(RuntimeError, match="session"):
        SysLogService().add("x")


# --- avantfaxlog ---------------------------------------------------------------------------

def test_avantfaxlog_writes_to_the_given_session(dbsession):
    from namifax.common.helpers import avantfaxlog

    avantfaxlog("notify> Executing: q1 done", session=dbsession)
    assert [r["logtext"] for r in _rows(dbsession, kw="executing")] == ["notify> Executing: q1 done"]


def test_avantfaxlog_still_writes_to_the_os_syslog_and_echoes(dbsession, capsys):
    from namifax.common.helpers import avantfaxlog

    with patch("namifax.common.helpers.syslog") as os_syslog:
        avantfaxlog("hello log", echo=True, session=dbsession)
    os_syslog.syslog.assert_called_once()
    assert "hello log" in capsys.readouterr().out


def test_avantfaxlog_in_a_cli_process_writes_to_the_configured_database(app, dbengine):
    """No session (hook processes): the entry goes to the database named by the environment."""
    from namifax.common.helpers import avantfaxlog

    avantfaxlog("cron> purged 3 faxes")
    with Session(dbengine) as session:
        assert [r["logtext"] for r in _rows(session, kw="purged")] == ["cron> purged 3 faxes"]


def test_avantfaxlog_never_raises_when_the_database_is_unavailable(monkeypatch):
    from namifax.common.helpers import avantfaxlog

    monkeypatch.setenv("DATABASE_URL", "sqlite:////nonexistent-dir/nami.db")
    avantfaxlog("must not break the caller")  # no exception


def test_avantfaxlog_never_raises_when_the_insert_fails(dbsession):
    from namifax.common.helpers import avantfaxlog
    from namifax.services.syslog import SysLogService

    with patch.object(SysLogService, "add", side_effect=RuntimeError("disk full")):
        avantfaxlog("still fine", session=dbsession)  # no exception


# --- the hooks really log -------------------------------------------------------------------

def test_a_cli_hook_leaves_a_trace_in_the_admin_log(app, dbengine, tmp_path):
    """faxrcvd logs a missing TIFF; the line is stored where the System Logs page reads it."""
    from namifax.cli import faxrcvd

    missing = tmp_path / "gone.tif"
    with patch.object(faxrcvd, "FaxModem"):          # run like the real hook: it opens its own session on the database
        assert faxrcvd.run_faxrcvd(["faxrcvd.py", str(missing), "ttyS0", "comm1", "none"]) == 0

    with Session(dbengine) as session:
        assert any("not found" in r["logtext"] for r in _rows(session, kw="gone.tif"))


# --- inside a running command-line unit ----------------------------------------------------------

def test_logging_inside_a_cli_session_uses_that_session(tmp_path):
    """A second writing connection would be locked out by the unit's pending write on SQLite."""
    from sqlalchemy import text

    from namifax.common.helpers import avantfaxlog
    from namifax.db.provider import cli_session
    from namifax.services.syslog import SysLogService

    env = {"DATABASE_URL": f"sqlite:///{tmp_path / 'u.db'}"}
    with cli_session(environ=env, ensure_schema=True) as session:
        session.execute(text("INSERT INTO SystemConfig (key, value) VALUES ('pending', 'write')"))
        avantfaxlog("logged inside the unit")
        assert [r["logtext"] for r in SysLogService(session).search(kw="inside the unit")] == ["logged inside the unit"]
    with Session(__import__("sqlalchemy").create_engine(env["DATABASE_URL"])) as session:
        assert [r["logtext"] for r in _rows(session, kw="inside the unit")] == ["logged inside the unit"]


def test_the_active_session_is_forgotten_when_it_ends(tmp_path):
    from namifax.db.provider import active_session, cli_session

    env = {"DATABASE_URL": f"sqlite:///{tmp_path / 'u.db'}"}
    assert active_session() is None
    with cli_session(environ=env, ensure_schema=True) as session:
        assert active_session() is session
    assert active_session() is None


def test_send_mail_inside_a_cli_session_reads_the_gateway_through_that_session(tmp_path):
    from unittest.mock import patch

    from sqlalchemy import text

    from namifax.common.helpers import send_mail
    from namifax.db.provider import cli_session
    from namifax.services.mailer import MailerService
    from namifax.services.smtp_settings import SmtpSettingsService

    env = {"DATABASE_URL": f"sqlite:///{tmp_path / 'u.db'}"}
    with cli_session(environ=env, ensure_schema=True) as session:
        SmtpSettingsService(session).save_settings({"smtp_host": "uncommitted.gateway.test", "smtp_port": 2525})
        with patch.object(MailerService, "sendmail", autospec=True, return_value=True) as sendmail:
            send_mail("a@x.test", "hook@corp.test", "S", "B")
        # the settings were not committed yet: only the unit's own session can see them
        assert sendmail.call_args.args[0].smtp_server == "uncommitted.gateway.test"
