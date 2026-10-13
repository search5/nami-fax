"""Spec 39 section 3.2: mail is sent with the SMTP gateway saved in the database (fallback: local defaults)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from namifax.services.mailer import MailerService
from namifax.services.smtp_settings import SmtpSettingsService

SETTINGS = {"smtp_host": "smtp.gateway.test", "smtp_port": 2525, "smtp_security": "SSL", "smtp_auth": "on",
            "smtp_username": "gw-user", "smtp_password": "gw-pass", "from_email": "fax@gateway.test"}


def _capture():
    """Patch sendmail so the mailer instance the code built can be inspected."""
    return patch.object(MailerService, "sendmail", autospec=True, return_value=True)


# --- MailerService.get_active_mailer -------------------------------------------------------

def test_active_mailer_uses_the_saved_settings(dbsession):
    SmtpSettingsService(dbsession).save_settings(SETTINGS)
    mailer = MailerService.get_active_mailer(dbsession)
    assert (mailer.smtp_server, mailer.smtp_port, mailer.use_ssl, mailer.use_tls) == ("smtp.gateway.test", 2525, True, False)
    assert (mailer.smtp_user, mailer.smtp_password, mailer.admin_email) == ("gw-user", "gw-pass", "fax@gateway.test")


def test_active_mailer_falls_back_to_local_defaults_without_a_session():
    mailer = MailerService.get_active_mailer(None)
    assert (mailer.smtp_server, mailer.smtp_port, mailer.use_ssl) == (None, 25, False)


def test_active_mailer_falls_back_to_the_local_mta_when_the_database_is_unavailable(dbsession):
    """An unreadable database must not turn into a mail that is silently kept in memory."""
    with patch.object(SmtpSettingsService, "get_settings", side_effect=RuntimeError("database is down")):
        mailer = MailerService.get_active_mailer(dbsession)
    assert (mailer.smtp_server, mailer.smtp_port, mailer.spool_mode) == ("localhost", 25, False)


def test_a_mailer_without_a_server_keeps_messages_in_memory_and_says_so():
    """Documents why the fallback above matters: this is not a delivery."""
    mailer = MailerService()
    mailer.set_message("body", subject="s")
    assert mailer.sendmail("a@x.test") is True
    assert len(mailer.get_spooled_messages()) == 1


def test_from_settings_remains_as_an_alias(dbsession):
    SmtpSettingsService(dbsession).save_settings(SETTINGS)
    assert MailerService.from_settings(dbsession).smtp_server == "smtp.gateway.test"


# --- helpers.send_mail ---------------------------------------------------------------------

def test_send_mail_uses_the_gateway_from_the_given_session_and_the_per_message_sender(dbsession):
    from namifax.common.helpers import send_mail

    SmtpSettingsService(dbsession).save_settings(SETTINGS)
    with _capture() as sendmail:
        assert send_mail("a@x.test, b@x.test", "user@corp.test", "Subject", "Body", session=dbsession) is True
    mailer = sendmail.call_args.args[0]
    assert (mailer.smtp_server, mailer.smtp_port, mailer.use_ssl) == ("smtp.gateway.test", 2525, True)
    assert mailer.admin_email == "user@corp.test"  # the sender of this message, as in the legacy send_mail
    assert sendmail.call_args.args[1] == ["a@x.test", "b@x.test"]


def test_send_mail_without_a_sender_uses_the_configured_from_address(dbsession):
    from namifax.common.helpers import send_mail

    SmtpSettingsService(dbsession).save_settings(SETTINGS)
    with _capture() as sendmail:
        send_mail("a@x.test", None, "Subject", "Body", session=dbsession)
    assert sendmail.call_args.args[0].admin_email == "fax@gateway.test"


def test_send_mail_in_a_cli_process_reads_the_configured_database(app, dbengine):
    """No session passed (CLI hooks): the settings come from the database named by the environment."""
    from namifax.common.helpers import send_mail

    with Session(dbengine) as session:
        SmtpSettingsService(session).save_settings(SETTINGS)
        session.commit()
    with _capture() as sendmail:
        send_mail("a@x.test", "hook@corp.test", "Subject", "Body")
    mailer = sendmail.call_args.args[0]
    assert (mailer.smtp_server, mailer.smtp_port) == ("smtp.gateway.test", 2525)
    assert mailer.admin_email == "hook@corp.test"


def test_send_mail_uses_the_local_mta_when_the_database_is_unreachable(monkeypatch):
    from namifax.common.helpers import send_mail

    monkeypatch.setenv("DATABASE_URL", "sqlite:////nonexistent-dir/nami.db")
    with _capture() as sendmail:
        assert send_mail("a@x.test", "hook@corp.test", "Subject", "Body") is True
    mailer = sendmail.call_args.args[0]
    assert (mailer.smtp_server, mailer.smtp_port) == ("localhost", 25)
    assert mailer.admin_email == "hook@corp.test"


# --- web: "email this fax" modal -----------------------------------------------------------

def _modal_request(dbsession, params, identity=None):
    from pyramid import testing

    class _Request(testing.DummyRequest):
        pass

    _Request.identity = identity or {"username": "admin", "uid": 1, "is_admin": True, "superuser": True}
    req = _Request()
    req.db, req.dbsession = object(), dbsession
    req.method, req.params = "POST", params
    return req






def test_the_modal_no_longer_calls_a_mailer_method_that_does_not_exist():
    assert not hasattr(MailerService, "send_mail")  # the old modal called mailer.send_mail(...), an AttributeError
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2] / "src/namifax/views/modals.py").read_text()
    assert "mailer.send_mail" not in src


# --- end to end over a real socket -----------------------------------------------------------

class _FakeSmtpServer:
    """Minimal SMTP server that records the messages it receives."""

    def __init__(self):
        import socket
        import threading

        self.messages = []
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            with conn:
                self._handle(conn)

    def _handle(self, conn):
        f = conn.makefile("rwb")

        def send(line):
            f.write(line.encode() + b"\r\n")
            f.flush()

        send("220 fake ESMTP")
        data_mode, lines = False, []
        for raw in f:
            line = raw.decode(errors="replace").rstrip("\r\n")
            if data_mode:
                if line == ".":
                    self.messages.append("\n".join(lines))
                    data_mode, lines = False, []
                    send("250 queued")
                else:
                    lines.append(line)
                continue
            cmd = line.upper()
            if cmd.startswith("EHLO") or cmd.startswith("HELO"):
                send("250 fake")
            elif cmd.startswith("DATA"):
                data_mode = True
                send("354 end with <CRLF>.<CRLF>")
            elif cmd.startswith("QUIT"):
                send("221 bye")
                return
            else:
                send("250 ok")

    def close(self):
        self._sock.close()


def test_a_mail_is_delivered_to_the_gateway_saved_in_the_database(app, dbengine, monkeypatch):
    """The administrator saves a gateway; a hook process (no web request) sends through it."""
    import socket

    from namifax.common.helpers import send_mail

    # smtplib resolves the local host name for EHLO; avoid a slow DNS lookup on machines without one
    monkeypatch.setattr(socket, "getfqdn", lambda *a: "localhost")
    monkeypatch.setattr(socket, "gethostbyname", lambda *a: "127.0.0.1")

    server = _FakeSmtpServer()
    try:
        with Session(dbengine) as session:
            SmtpSettingsService(session).save_settings({
                "smtp_host": "127.0.0.1", "smtp_port": server.port, "smtp_security": "NONE",
                "from_email": "fax@gateway.test"})
            session.commit()

        assert send_mail("rcpt@example.test", "hook@corp.test", "Gateway check", "It works") is True
    finally:
        server.close()

    assert len(server.messages) == 1
    assert "Subject: Gateway check" in server.messages[0]
    assert "hook@corp.test" in server.messages[0]
