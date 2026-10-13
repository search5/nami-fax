"""HylaFAX users follow the AvantFAX accounts (the original's faxadduser/faxdeluser calls through sudo): switched on with
HYLAFAX_USER_SYNC, the commands run without a shell, a failing command never breaks the account change."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from namifax.services import hylafax_users
from namifax.services.user_account import NFUserAccount


@pytest.fixture
def run(monkeypatch):
    monkeypatch.setenv("HYLAFAX_USER_SYNC", "1")
    monkeypatch.setenv("SUDO", "sudo")
    monkeypatch.setenv("HYLAFAX_PREFIX", "/usr")
    with patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock:
        yield mock


def _commands(run):
    return [c.args[0] for c in run.call_args_list]


def test_it_is_off_by_default(monkeypatch):
    monkeypatch.delenv("HYLAFAX_USER_SYNC", raising=False)
    with patch("subprocess.run") as run:
        hylafax_users.add_user(5, "jdoe", "Secret123!")
        hylafax_users.remove_user("jdoe")
    assert not run.called


def test_adding_a_user_runs_faxadduser_like_the_original(run):
    hylafax_users.add_user(5, "jdoe", "Secret123!")
    assert _commands(run) == [["sudo", "/usr/sbin/faxadduser", "-u", "5", "-p", "Secret123!", "jdoe"]]
    assert run.call_args.kwargs.get("shell") in (None, False)


def test_removing_a_user_runs_faxdeluser(run):
    hylafax_users.remove_user("jdoe")
    assert _commands(run) == [["sudo", "/usr/sbin/faxdeluser", "jdoe"]]


def test_a_new_password_replaces_the_hylafax_user(run):
    hylafax_users.change_password(5, "jdoe", "NewSecret123!")
    assert _commands(run) == [["sudo", "/usr/sbin/faxdeluser", "jdoe"],
                              ["sudo", "/usr/sbin/faxadduser", "-u", "5", "-p", "NewSecret123!", "jdoe"]]


def test_a_missing_program_is_reported_not_raised(run):
    run.side_effect = FileNotFoundError("sudo")
    assert hylafax_users.add_user(5, "jdoe", "Secret123!") is False


def test_creating_an_account_adds_the_hylafax_user(run, dbsession):
    svc = NFUserAccount(db=dbsession)
    assert svc.create({"username": "syncd", "password": "Secret123!", "email": "s@x.test", "name": "S", "acc_enabled": 1})
    assert any(c[1:2] == ["/usr/sbin/faxadduser"] and c[-1] == "syncd" and c[c.index("-p") + 1] == "Secret123!" for c in _commands(run))


def test_a_generated_password_is_the_one_given_to_hylafax(run, dbsession):
    svc = NFUserAccount(db=dbsession)
    assert svc.create({"username": "syncg", "password": "", "email": "g@x.test", "name": "G", "acc_enabled": 1})
    add = next(c for c in _commands(run) if c[1:2] == ["/usr/sbin/faxadduser"])
    assert add[add.index("-p") + 1] == svc.generated_password


def test_changing_the_password_updates_the_hylafax_user(run, dbsession):
    svc = NFUserAccount(db=dbsession)
    assert svc.create({"username": "syncc", "password": "Secret123!", "email": "c@x.test", "name": "C", "acc_enabled": 1,
                       "last_login": "2026-01-01 10:00:00"})
    run.reset_mock()
    assert svc.change_password("Another456!")
    cmds = _commands(run)
    assert cmds[0][1:] == ["/usr/sbin/faxdeluser", "syncc"] and cmds[1][-3:] == ["Another456!", "syncc"][-3:] or "Another456!" in cmds[1]


def test_removing_an_account_removes_the_hylafax_user(run, dbsession):
    svc = NFUserAccount(db=dbsession)
    assert svc.create({"username": "syncr", "password": "Secret123!", "email": "r@x.test", "name": "R", "acc_enabled": 1})
    run.reset_mock()
    assert svc.remove(svc.uid)
    assert _commands(run) == [["sudo", "/usr/sbin/faxdeluser", "syncr"]]


def test_a_reset_password_updates_the_hylafax_user(run, dbsession):
    svc = NFUserAccount(db=dbsession)
    assert svc.create({"username": "syncp", "password": "Secret123!", "email": "p@x.test", "name": "P", "acc_enabled": 1})
    run.reset_mock()
    ok, new_pwd = NFUserAccount(db=dbsession).reset_password("p@x.test")
    assert ok and any(new_pwd in c for c in _commands(run))
