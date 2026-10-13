"""MAX_USERNAME_SIZE, MAX_PASSWD_SIZE, MIN_PASSWD_SIZE and MAX_EMAIL_SIZE of the original's local_config.php.

The defaults are the original's (15, 15, 8, 99) and each can be changed from the environment under the same name. The password
limits are enforced when a password is set; the user name and e-mail limits are the length limits of the entry fields.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from namifax.common import settings
from namifax.services.user_account import NFUserAccount

NAMES = ("MAX_USERNAME_SIZE", "MAX_PASSWD_SIZE", "MIN_PASSWD_SIZE", "MAX_EMAIL_SIZE")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)


# --- the settings ------------------------------------------------------------------------------------------------------------

def test_the_defaults_are_the_originals():
    assert (settings.max_username_size(), settings.max_passwd_size(), settings.min_passwd_size(), settings.max_email_size()) \
        == (15, 15, 8, 99)


@pytest.mark.parametrize("name,reader", [("MAX_USERNAME_SIZE", settings.max_username_size),
                                         ("MAX_PASSWD_SIZE", settings.max_passwd_size),
                                         ("MIN_PASSWD_SIZE", settings.min_passwd_size),
                                         ("MAX_EMAIL_SIZE", settings.max_email_size)])
def test_a_limit_is_set_from_the_environment(monkeypatch, name, reader):
    monkeypatch.setenv(name, "33")
    assert reader() == 33


def test_a_value_that_is_not_a_number_is_ignored(monkeypatch):
    monkeypatch.setenv("MAX_PASSWD_SIZE", "many")
    assert settings.max_passwd_size() == 15


# --- the password rules ------------------------------------------------------------------------------------------------------

@pytest.fixture
def user(dbsession):
    svc = NFUserAccount(db=dbsession)
    assert svc.create({"username": "limits", "password": "Secret123!", "email": "limits@corp.test", "name": "Limits",
                       "last_login": "2026-01-01 10:00:00", "acc_enabled": 1}), svc.error
    dbsession.flush()
    return svc


def test_a_password_of_16_characters_is_too_long_by_default(user):
    assert user.change_password("Abcdefgh1234567!") is False and "too long (maximum 15" in user.error


def test_a_password_of_15_characters_is_accepted_by_default(user):
    assert user.change_password("Abcdefgh123456!") is True


def test_the_longest_password_can_be_raised(user, monkeypatch):
    monkeypatch.setenv("MAX_PASSWD_SIZE", "64")
    assert user.change_password("Abcdefgh1234567890-long!") is True


def test_the_shortest_password_can_be_changed(user, monkeypatch):
    monkeypatch.setenv("MIN_PASSWD_SIZE", "12")
    assert user.change_password("Short-pw1!") is False and "minimum 12" in user.error


# --- the entry fields --------------------------------------------------------------------------------------------------------

def test_the_user_form_fields_carry_the_limits(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    soup = BeautifulSoup(testapp.get("/admin/users").text, "html.parser")
    assert [soup.find("input", {"name": n})["maxlength"] for n in ("username", "password", "email")] == ["15", "15", "99"]


def test_the_field_limits_follow_the_environment(testapp, monkeypatch):
    monkeypatch.setenv("MAX_USERNAME_SIZE", "20")
    monkeypatch.setenv("MAX_EMAIL_SIZE", "120")
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    soup = BeautifulSoup(testapp.get("/admin/users").text, "html.parser")
    assert [soup.find("input", {"name": n})["maxlength"] for n in ("username", "email")] == ["20", "120"]
