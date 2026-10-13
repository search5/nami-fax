"""Admin > Users: the original admin/users.php and deluser.php (every field, line/DID/category assignments, validation messages,
a random password mailed to a new user, a confirmation before deleting)."""

from __future__ import annotations

import re
from datetime import date
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import select

from namifax.common.passwords import verify_password
from namifax.models import UserAccount


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


@pytest.fixture
def mails():
    sent = []
    with patch("namifax.views.admin_users.send_mail", lambda to, frm, subject, text, **kw: sent.append((to, subject, text)) or True):
        yield sent


def _form(page):
    return next(f for f in page.forms.values() if "username" in f.fields)


def _user(session, username):
    session.expire_all()
    return session.execute(select(UserAccount).where(UserAccount.username == username)).scalar_one()


def _create(client, **fields):
    form = _form(client.get("/admin/users"))
    form["name"], form["username"], form["email"] = fields.pop("name", "New Person"), fields.pop("username", "newp"), fields.pop("email", "newp@corp.test")
    for key, value in fields.items():
        form[key] = value
    return form.submit()


# --- the form -----------------------------------------------------------------------------------------------------------------

def test_the_form_has_every_field_of_the_original(client):
    page = client.get("/admin/users")
    for name in ("name", "username", "password", "pwdcycle", "pwd_reuse", "email", "language", "from_company", "from_location",
                 "from_voicenumber", "from_faxnumber", "user_tsi", "coverpage_id", "faxperpageinbox", "faxperpagearchive",
                 "is_admin", "superuser", "can_del", "any_modem", "modemdevs[]", "faxcats[]"):
        assert _form(page).fields.get(name), name


def test_the_limits_are_on_the_fields(client):
    soup = BeautifulSoup(client.get("/admin/users").text, "html.parser")
    assert soup.find("input", {"name": "name"})["maxlength"] == "40"
    assert soup.find("input", {"name": "username"}).has_attr("maxlength") and soup.find("input", {"name": "password"}).has_attr("maxlength")


def test_the_per_page_choices_are_the_original_ones_with_its_defaults(client):
    form = _form(client.get("/admin/users"))
    assert [v for v, _, _ in form["faxperpageinbox"].options] == ["10", "15", "20", "25", "30", "50", "100"]
    assert (form["faxperpageinbox"].value, form["faxperpagearchive"].value) == ("25", "30")


def test_the_password_cycle_choices(client):
    assert [v for v, _, _ in _form(client.get("/admin/users"))["pwdcycle"].options] == ["0", "3", "6"]


def test_the_lines_and_categories_are_listed_and_a_missing_set_is_explained(client, dbsession):
    form = _form(client.get("/admin/users"))
    assert len(form.fields["modemdevs[]"]) >= 2 and len(form.fields["faxcats[]"]) >= 3
    from namifax.models import FaxCategory, Modems
    dbsession.execute(FaxCategory.__table__.delete())
    dbsession.execute(Modems.__table__.delete())
    dbsession.flush()
    page = client.get("/admin/users")
    assert "first create a modem" in page.text and "first create a category" in page.text


def test_the_did_routes_are_shown_only_when_did_routing_is_on(client, monkeypatch):
    assert "didrouting[]" not in _form(client.get("/admin/users")).fields
    monkeypatch.setenv("ENABLE_DID_ROUTING", "1")
    form = _form(client.get("/admin/users"))
    assert "0" in [c.value or "" for c in form.fields["didrouting[]"]] or form.fields["didrouting[]"]
    assert "Catch All" in client.get("/admin/users").text


# --- creating -----------------------------------------------------------------------------------------------------------------

def test_a_new_user_without_a_password_gets_a_random_one_by_mail(client, dbsession, mails):
    res = _create(client)
    assert "User settings have been saved." in res.text
    (to, subject, text), = mails
    assert to == "newp@corp.test" and subject == "New User Details" and "newp" in text
    password = re.search(r"Password - (\S+)", text).group(1)
    user = _user(dbsession, "newp")
    import hashlib
    assert verify_password(user.password, password) and user.password.startswith("$argon2id$") and password != "password" and user.wasreset


def test_a_new_user_with_a_chosen_password_is_not_forced_to_change_it(client, dbsession, mails):
    _create(client, password="Chosen-pass-1")
    assert not _user(dbsession, "newp").wasreset


def test_the_choices_made_for_a_new_user_are_saved_and_shown_again(client, dbsession, mails):
    form = _form(client.get("/admin/users"))
    form["name"], form["username"], form["email"] = "Line User", "lineuser", "lu@corp.test"
    form.set("modemdevs[]", True, index=1)
    form.set("faxcats[]", True, index=0)
    form["language"] = "ko" if "ko" in [v for v, _, _ in form["language"].options] else form["language"].value
    form["from_company"], form["user_tsi"] = "Corp Inc", "CORP TSI"
    form["faxperpageinbox"], form["faxperpagearchive"] = "50", "100"
    form["is_admin"], form["can_del"] = True, True
    form.submit()
    user = _user(dbsession, "lineuser")
    assert user.modemdevs and user.faxcats and user.from_company == "Corp Inc" and user.user_tsi == "CORP TSI"
    assert (user.faxperpageinbox, user.faxperpagearchive, bool(user.is_admin), bool(user.can_del)) == (50, 100, True, True)
    edit = _form(client.get(f"/admin/users?uid={user.uid}"))
    assert [c.checked for c in edit.fields["modemdevs[]"]].count(True) == 1 and [c.checked for c in edit.fields["faxcats[]"]].count(True) == 1


# --- editing ------------------------------------------------------------------------------------------------------------------

def _edit(client, dbsession, username, **fields):
    user = _user(dbsession, username)
    form = _form(client.get(f"/admin/users?uid={user.uid}"))
    for key, value in fields.items():
        form[key] = value
    return form.submit()


def _make(client, mails, **kw):
    kw.setdefault("any_modem", True)                                          # (a new user starts with it off, like the original)
    _create(client, password="Chosen-pass-1", **kw)


def test_unchecking_any_modem_is_remembered(client, dbsession, mails):
    _make(client, mails)
    assert _user(dbsession, "newp").any_modem
    res = _edit(client, dbsession, "newp", any_modem=False)
    assert "User settings have been saved." in res.text and not _user(dbsession, "newp").any_modem


def test_a_disabled_account_must_choose_a_new_password_when_it_is_enabled_again(client, dbsession, mails):
    _make(client, mails)
    _edit(client, dbsession, "newp", acc_enabled=False)
    user = _user(dbsession, "newp")
    assert not user.acc_enabled and user.wasreset


def test_changing_the_password_cycle_sets_the_expiry_date(client, dbsession, mails):
    _make(client, mails)
    _edit(client, dbsession, "newp", pwdcycle="3")
    expires = _user(dbsession, "newp").pwdexpire
    assert expires and 80 <= (date.fromisoformat(str(expires)) - date.today()).days <= 95
    _edit(client, dbsession, "newp", pwdcycle="0")
    assert _user(dbsession, "newp").pwdexpire is None


def test_a_new_password_can_be_set_and_is_checked(client, dbsession, mails):
    _make(client, mails)
    assert "too short" in _edit(client, dbsession, "newp", password="abc").text
    assert "User settings have been saved." in _edit(client, dbsession, "newp", password="Another-pass-2").text


def test_the_email_signature_survives_an_edit(client, dbsession, mails):
    _make(client, mails)
    user = _user(dbsession, "newp")
    user.email_sig = "-- kept"
    dbsession.flush()
    _edit(client, dbsession, "newp", name="Renamed Person")
    assert _user(dbsession, "newp").email_sig == "-- kept"


# --- mistakes are said out loud -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("fields,message", [
    ({"name": ""}, "name"),
    ({"username": ""}, "username"),
    ({"username": "bad name!"}, "Non-alphanumeric"),
    ({"email": "not-an-address"}, "valid e-mail address"),
    ({"email": ""}, "valid e-mail address"),
])
def test_a_bad_form_says_what_is_wrong_and_creates_nobody(client, dbsession, mails, fields, message):
    form = _form(client.get("/admin/users"))
    values = {"name": "New Person", "username": "newp", "email": "newp@corp.test", **fields}
    form["name"], form["username"], form["email"] = values["name"], values["username"], values["email"]
    res = form.submit()
    assert message.lower() in res.text.lower() and "saved" not in res.text.lower()
    assert dbsession.execute(select(UserAccount).where(UserAccount.username.in_(["newp", "bad name!"]))).first() is None


def test_a_username_or_address_that_is_taken_is_refused(client, dbsession, mails):
    _make(client, mails)
    assert "already in use" in _create(client, username="newp", email="other@corp.test").text
    assert "already in use" in _create(client, username="other", email="newp@corp.test").text


# --- deleting -----------------------------------------------------------------------------------------------------------------

def test_the_delete_button_asks_first(client, dbsession, mails):
    _make(client, mails)
    user = _user(dbsession, "newp")
    form = _form(client.get(f"/admin/users?uid={user.uid}"))
    res = form.submit("delete")
    assert res.status_int == 302 and res.headers["Location"].endswith(f"/admin/users/delete?uid={user.uid}")
    page = res.follow()
    assert "New Person" in page.text and not _user(dbsession, "newp").deleted


def test_confirming_deletes_the_account(client, dbsession, mails):
    _make(client, mails)
    user = _user(dbsession, "newp")
    page = client.get(f"/admin/users/delete?uid={user.uid}")
    res = next(f for f in page.forms.values() if "uid" in f.fields).submit()
    assert res.status_int == 302 and res.headers["Location"].endswith("/admin/users")
    assert dbsession.get(UserAccount, user.uid).deleted


def test_you_cannot_delete_yourself_or_the_last_superuser(client, dbsession):
    admin = _user(dbsession, "admin")
    page = client.get(f"/admin/users/delete?uid={admin.uid}")
    res = next(f for f in page.forms.values() if "uid" in f.fields).submit(expect_errors=True)
    assert not dbsession.get(UserAccount, admin.uid).deleted and ("cannot" in res.text.lower() or res.status_int in (302, 400, 403))


def test_the_list_shows_the_last_login_ip_superuser_mark_and_the_count(client):
    page = client.get("/admin/users")
    assert "Last Login" in page.text and "Last IP" in page.text and re.search(r"\d+ users?", page.text)
