"""Demo accounts and sample data exist only when asked for; a new database never starts with a known password."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
import webtest

from namifax.db.bootstrap import ensure_schema
from namifax.db.provider import create_sa_engine


def _count(engine, table):
    with engine.connect() as c:
        return c.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()


@pytest.fixture
def no_demo(monkeypatch):
    monkeypatch.delenv("NAMIFAX_DEMO_DATA", raising=False)


def test_a_new_sqlite_database_has_no_users_or_samples_by_default(tmp_path, no_demo):
    engine = create_sa_engine(f"sqlite:///{tmp_path / 'a.db'}")
    ensure_schema(engine)
    assert [_count(engine, t) for t in ("UserAccount", "AddressBook", "FaxArchive", "Modems", "DIDRoute", "SysLog")] == [0] * 6
    assert (_count(engine, "FaxCategory"), _count(engine, "CoverPages")) == (0, 3)        # the original's three cover pages
    engine.dispose()


@pytest.mark.parametrize("value", ["1", "true", "yes", "on"])
def test_the_environment_switch_turns_the_demo_data_on(tmp_path, monkeypatch, value):
    monkeypatch.setenv("NAMIFAX_DEMO_DATA", value)
    engine = create_sa_engine(f"sqlite:///{tmp_path / 'b.db'}")
    ensure_schema(engine)
    assert _count(engine, "UserAccount") == 2 and _count(engine, "FaxArchive") == 2
    engine.dispose()


@pytest.mark.parametrize("value", ["0", "false", "no", "", "maybe"])
def test_anything_else_keeps_it_off(tmp_path, monkeypatch, value):
    monkeypatch.setenv("NAMIFAX_DEMO_DATA", value)
    engine = create_sa_engine(f"sqlite:///{tmp_path / 'c.db'}")
    ensure_schema(engine)
    assert _count(engine, "UserAccount") == 0
    engine.dispose()


def test_the_ini_setting_works_too(tmp_path, no_demo):
    from namifax import create_app

    app = create_app(**{"sqlalchemy.url": f"sqlite:///{tmp_path / 'd.db'}", "demo.data": "true"})
    assert _count(app.registry["dbengine"], "UserAccount") == 2


def test_the_switch_never_touches_a_database_that_already_has_users(tmp_path, monkeypatch, no_demo):
    engine = create_sa_engine(f"sqlite:///{tmp_path / 'e.db'}")
    ensure_schema(engine)
    with engine.begin() as c:
        c.execute(sa.text("INSERT INTO UserAccount (uid, username, password, email) VALUES (1, 'real', 'x', 'r@x.test')"))
    monkeypatch.setenv("NAMIFAX_DEMO_DATA", "1")
    ensure_schema(engine)
    assert _count(engine, "UserAccount") == 1 and _count(engine, "FaxArchive") == 0
    engine.dispose()


def test_nobody_can_log_in_with_the_old_demo_password_on_a_default_start(tmp_path, no_demo):
    from namifax import create_app

    app = create_app(**{"sqlalchemy.url": f"sqlite:///{tmp_path / 'f.db'}"})
    client = webtest.TestApp(app, extra_environ={"HTTP_HOST": "example.com"})
    res = client.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    assert res.status_int == 200 and "Invalid username or password" in res.text
    assert client.get("/inbox", expect_errors=True).status_int != 200


def test_the_demo_data_is_not_created_on_servers_even_if_asked(monkeypatch):
    """Servers get no demo accounts under any setting (the sample rows use fixed ids)."""
    from namifax.db import bootstrap

    assert bootstrap.demo_data_wanted("postgresql", {"demo.data": "true"}, {"NAMIFAX_DEMO_DATA": "1"}) is False
    assert bootstrap.demo_data_wanted("mysql", {}, {"NAMIFAX_DEMO_DATA": "1"}) is False
    assert bootstrap.demo_data_wanted("sqlite", {}, {"NAMIFAX_DEMO_DATA": "1"}) is True


# --- createuser: no built-in password ----------------------------------------------------------------------------------

def test_createuser_refuses_to_guess_a_password(tmp_path, monkeypatch, capsys, no_demo):
    from namifax.cli.user import run_createuser

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'g.db'}")
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    assert run_createuser(["-u", "boss"]) == 2
    assert "password" in capsys.readouterr().out.lower()
    engine = create_sa_engine(f"sqlite:///{tmp_path / 'g.db'}")
    ensure_schema(engine)
    assert _count(engine, "UserAccount") == 0
    engine.dispose()


def test_createuser_asks_for_the_password_when_run_by_a_person(tmp_path, monkeypatch, no_demo):
    from namifax.cli import user as user_mod

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'h.db'}")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    answers = iter(["Secret123!", "Secret123!"])
    monkeypatch.setattr(user_mod.getpass, "getpass", lambda prompt="": next(answers))
    assert user_mod.run_createuser(["-u", "boss"]) == 0
    engine = create_sa_engine(f"sqlite:///{tmp_path / 'h.db'}")
    assert _count(engine, "UserAccount") == 1
    engine.dispose()


def test_a_mistyped_confirmation_creates_nothing(tmp_path, monkeypatch, capsys, no_demo):
    from namifax.cli import user as user_mod

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'i.db'}")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    answers = iter(["Secret123!", "Different456!"])
    monkeypatch.setattr(user_mod.getpass, "getpass", lambda prompt="": next(answers))
    assert user_mod.run_createuser(["-u", "boss"]) == 2
    assert "match" in capsys.readouterr().out.lower()


def test_a_short_password_is_refused(tmp_path, monkeypatch, capsys, no_demo):
    from namifax.cli.user import run_createuser

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'j.db'}")
    assert run_createuser(["-u", "boss", "-p", "short"]) == 2
    assert "at least" in capsys.readouterr().out


def test_the_password_can_come_from_the_environment_for_scripted_installs(tmp_path, monkeypatch, no_demo):
    from namifax.cli.user import run_createuser

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'k.db'}")
    monkeypatch.setenv("NAMIFAX_NEW_USER_PASSWORD", "FromTheEnvironment1!")
    assert run_createuser(["-u", "boss"]) == 0
    from sqlalchemy.orm import Session

    from namifax.services.user_account import NFUserAccount

    engine = create_sa_engine(f"sqlite:///{tmp_path / 'k.db'}")
    with Session(engine) as s:
        assert NFUserAccount(db=s).login("boss", "FromTheEnvironment1!") is True
    engine.dispose()


def test_createuser_can_reset_the_password_of_an_existing_account(tmp_path, monkeypatch):
    """A forgotten administrator password must be recoverable from the command line (it used to need the old one)."""
    from sqlalchemy.orm import Session

    from namifax.cli.user import run_createuser
    from namifax.services.user_account import NFUserAccount

    monkeypatch.delenv("NAMIFAX_DEMO_DATA", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'l.db'}")
    assert run_createuser(["-u", "boss", "-p", "FirstPassword1!"]) == 0
    assert run_createuser(["-u", "boss", "-p", "SecondPass2!"]) == 0
    engine = create_sa_engine(f"sqlite:///{tmp_path / 'l.db'}")
    with Session(engine) as s:
        assert NFUserAccount(db=s).login("boss", "SecondPass2!") is True
        assert NFUserAccount(db=s).login("boss", "FirstPassword1!") is False
    engine.dispose()
