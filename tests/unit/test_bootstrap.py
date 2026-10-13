"""Starting the application on any supported database (SQLite, MySQL, MariaDB, PostgreSQL)."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
import webtest
from sqlalchemy.orm import Session

from namifax.db.provider import create_sa_engine


def _tables(engine):
    return set(sa.inspect(engine).get_table_names())


def _alembic_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config()
    cfg.set_main_option("script_location", "namifax:alembic")
    return ScriptDirectory.from_config(cfg).get_current_head()


def _model_tables():
    import namifax.models  # noqa: F401
    from namifax.models.meta import Base

    return {t.name for t in Base.metadata.sorted_tables}


# --- SQLite keeps the legacy path (and the demo data) -------------------------------------------------------

def test_sqlite_creates_every_table_and_the_demo_data(tmp_path):
    from namifax.db.bootstrap import ensure_schema

    engine = create_sa_engine(f"sqlite:///{tmp_path / 'a.db'}")
    ensure_schema(engine)
    assert _model_tables() <= _tables(engine)
    with engine.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM UserAccount")).scalar() == 2
    ensure_schema(engine)                                   # idempotent
    with engine.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM UserAccount")).scalar() == 2
    engine.dispose()


def test_a_failure_to_initialise_is_loud(tmp_path, monkeypatch):
    from namifax.db import bootstrap

    def boom(engine):
        raise sa.exc.OperationalError("CREATE TABLE", {}, Exception("disk is full"))

    monkeypatch.setattr(bootstrap, "upgrade_to_head", boom)
    engine = create_sa_engine(f"sqlite:///{tmp_path / 'b.db'}")
    with pytest.raises(RuntimeError, match="initialisation failed"):
        bootstrap.ensure_schema(engine)
    engine.dispose()


def test_alembic_environment_accepts_an_existing_connection(tmp_path):
    """Programmatic upgrades hand env.py the connection; there is no ini file to read."""
    import alembic.command
    from alembic.config import Config

    engine = create_sa_engine(f"sqlite:///{tmp_path / 'c.db'}")
    cfg = Config()
    cfg.set_main_option("script_location", "namifax:alembic")
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        alembic.command.upgrade(cfg, "head")
    assert _model_tables() <= _tables(engine) | {"alembic_version"}
    engine.dispose()


# --- real servers --------------------------------------------------------------------------------------------

@pytest.mark.serverdb
def test_server_database_gets_the_schema_and_default_records_only(server_db_url):
    from namifax.db.bootstrap import ensure_schema

    engine = create_sa_engine(server_db_url)
    try:
        ensure_schema(engine)
        assert _model_tables() <= _tables(engine)
        with engine.connect() as c:
            assert c.execute(sa.text("SELECT version_num FROM alembic_version")).scalar() == _alembic_head()
        with Session(engine) as s:
            from namifax.models import CoverPages, FaxCategory, UserAccount

            count = lambda m: s.execute(sa.select(sa.func.count()).select_from(m)).scalar()   # noqa: E731
            assert (count(FaxCategory), count(CoverPages)) == (0, 3)
            assert count(UserAccount) == 0                  # no demo accounts with a well-known password
        ensure_schema(engine)                               # a second start changes nothing
        with Session(engine) as s:
            assert s.execute(sa.select(sa.func.count()).select_from(FaxCategory)).scalar() == 0
    finally:
        engine.dispose()


@pytest.mark.serverdb
def test_the_application_runs_on_the_server_database(server_db_url):
    from namifax import create_app
    from namifax.models import UserAccount  # noqa: F401
    from namifax.services.user_account import NFUserAccount

    app = create_app(**{"sqlalchemy.url": server_db_url})
    engine = app.registry["dbengine"]
    with Session(engine) as s:
        assert NFUserAccount(db=s).create({"username": "boss", "password": "Secret123!", "email": "boss@x.test",
                                           "name": "Boss", "is_admin": 1, "superuser": 1, "acc_enabled": 1})
        s.commit()

    client = webtest.TestApp(app, extra_environ={"HTTP_HOST": "example.com"})
    # a new account must choose its own password before it gets in (the original AvantFAX does the same)
    res = client.post("/login", {"username": "boss", "password": "Secret123!", "_submit_check": "1"})
    assert res.status_int == 302 and res.headers["Location"].endswith("/pwdexpired"), res.text[:300]
    assert client.get("/inbox", expect_errors=True).status_int != 200
    res = client.post("/pwdexpired", {"oldpwd": "Secret123!", "newpwd": "My-own-pass-9", "conpwd": "My-own-pass-9"})
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox"), res.text[:300]
    bad = []
    for path in ("/inbox", "/archive", "/archive?sentrecvd=*", "/addressbook", "/distrolist", "/outbox", "/sendfax",
                 "/settings", "/admin", "/admin/users", "/admin/modems", "/admin/routing/did", "/admin/barcodes",
                 "/admin/covers", "/admin/categories", "/admin/dynconf", "/admin/system_logs", "/admin/smtp",
                 "/admin/printers", "/ajax/inbox", "/ajax/modemstatus", "/admin/storage", "/admin/saml", "/admin/fax2email",
                 "/admin/system_func", "/helper/distrocontacts", "/helper/faxcontacts", "/helper/emailcontacts",
                 "/ajax/book?q=a", "/ajax/archivebook?q=a", "/emailbook"):
        r = client.get(path, expect_errors=True)
        if r.status_int != 200:          # a redirect would mean "not logged in" (or a page that bailed out)
            bad.append((path, r.status_int, r.headers.get("Location")))
    assert bad == []

    # the flows that need the session cookie and the account service, on this database
    from unittest.mock import patch

    from namifax.services.totp import TotpService

    with Session(engine) as s:
        two = NFUserAccount(db=s)
        assert two.create({"username": "twofa", "password": "Secret123!", "email": "twofa@x.test", "acc_enabled": 1,
                            "last_login": "2026-01-01 10:00:00"})
        t = TotpService(s)
        with patch.object(t, "verify_code", return_value=True):
            codes = t.enable_totp(two.uid, t.generate_secret(), "123456")["backup_codes"]
        s.commit()
    second = webtest.TestApp(app, extra_environ={"HTTP_HOST": "example.com"})
    step = second.post("/login", {"username": "twofa", "password": "Secret123!", "_submit_check": "1"})
    assert step.headers["Location"].endswith("/login/totp")
    assert second.post("/login/totp", {"code": codes[0]}).status_int == 302
    assert second.get("/inbox", expect_errors=True).status_int == 200

    # turning 2FA on from the settings page (CSRF token, secret in the flow cookie, hashed recovery codes)
    import re

    import pyotp

    page = client.get("/settings/2fa/setup")
    secret = re.search(r'data-secret="([A-Z2-7]+)"', page.text).group(1)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    done = client.post("/settings/2fa/enable", {"csrf_token": token, "code": pyotp.TOTP(secret).now()})
    assert done.status_int == 200 and len(set(re.findall(r"\b[A-Z2-9]{5}-[A-Z2-9]{5}\b", done.text))) == 8

    third = webtest.TestApp(app, extra_environ={"HTTP_HOST": "example.com"})
    result = {"success": True, "name_id": "sso@x.test", "attributes": {"email": "sso@x.test", "displayName": "Sso User"}}
    with patch("namifax.services.saml.SAMLService.process_saml_response", return_value=result):
        assert third.post("/auth/saml/acs", {"SAMLResponse": "x"}).status_int == 302
    assert third.get("/inbox", expect_errors=True).status_int == 200
    assert third.get("/admin", expect_errors=True).status_int == 403
