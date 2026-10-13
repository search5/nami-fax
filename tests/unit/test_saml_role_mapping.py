"""Roles and attributes from the identity provider become the account's settings (admin, superuser, may delete, any line, lines,
categories) when the administrator turns the mapping on; with it off the account keeps what NamiFAX has."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from namifax.models import FaxCategory, UserAccount
from test_saml_security import (_post, _response, _signed_in, _start, client, configured, idp, person)  # noqa: F401


@pytest.fixture
def mapping(configured, dbsession):
    for key, value in (("saml_role_mapping", "1"), ("saml_role_attribute", "Role"), ("saml_role_admin", "namifax-admin"),
                       ("saml_role_superuser", "namifax-superuser"), ("saml_role_can_del", "namifax-can-delete"),
                       ("saml_role_any_modem", "namifax-any-modem"), ("saml_attr_modems", "modems"), ("saml_attr_faxcats", "faxcats")):
        configured.set(key, value)
    return configured


def _account(session):
    session.expire_all()
    return session.execute(select(UserAccount).where(UserAccount.username == "ssouser")).scalar_one()


def _login_with(client, idp, **attributes):
    request_id = _start(client)
    return _post(client, _response(idp, in_response_to=request_id, attributes=attributes))


def test_roles_set_the_flags(client, mapping, person, idp, dbsession):
    _login_with(client, idp, Role=["namifax-admin", "namifax-can-delete", "namifax-any-modem", "offline_access"])
    user = _account(dbsession)
    assert (bool(user.is_admin), bool(user.superuser), bool(user.can_del), bool(user.any_modem)) == (True, False, True, True)


def test_the_superuser_role(client, mapping, person, idp, dbsession):
    _login_with(client, idp, Role=["namifax-superuser"])
    user = _account(dbsession)
    assert bool(user.superuser) and bool(user.is_admin)                                  # a superuser can use the console too


def test_a_role_that_is_gone_takes_the_right_away(client, mapping, person, idp, dbsession):
    _login_with(client, idp, Role=["namifax-admin", "namifax-can-delete"])
    assert _account(dbsession).is_admin
    _login_with(client, idp, Role=["offline_access"])
    user = _account(dbsession)
    assert not user.is_admin and not user.can_del


def test_without_the_mapping_the_accounts_own_settings_stay(client, configured, person, idp, dbsession):
    dbsession.execute(UserAccount.__table__.update().where(UserAccount.username == "ssouser").values(is_admin=1, can_del=1))
    dbsession.flush()
    _login_with(client, idp, Role=["offline_access"])
    user = _account(dbsession)
    assert user.is_admin and user.can_del


def test_modems_and_categories_come_from_attributes(client, mapping, person, idp, dbsession):
    category = FaxCategory(name="Contracts")
    dbsession.add(category)
    dbsession.flush()
    _login_with(client, idp, Role=["x"], modems=["ttyS0", "ttyS1"], faxcats=["Contracts"])
    user = _account(dbsession)
    assert set(user.modemdevs.split("|")) == {"ttyS0", "ttyS1"} and user.faxcats == str(category.catid)


def test_unknown_modems_and_categories_are_ignored(client, mapping, person, idp, dbsession):
    _login_with(client, idp, Role=["x"], modems=["ttyS0", "nope"], faxcats=["No such category"])
    user = _account(dbsession)
    assert user.modemdevs == "ttyS0" and not user.faxcats


def test_a_blank_attribute_name_leaves_that_setting_alone(client, mapping, person, idp, dbsession):
    mapping.set("saml_attr_modems", "")
    dbsession.execute(UserAccount.__table__.update().where(UserAccount.username == "ssouser").values(modemdevs="ttyS1"))
    dbsession.flush()
    _login_with(client, idp, Role=["x"], modems=["ttyS0"])
    assert _account(dbsession).modemdevs == "ttyS1"


def test_a_new_account_made_at_the_first_login_gets_the_roles(client, mapping, idp, dbsession):
    mapping.set("saml_jit_provisioning", "1")
    request_id = _start(client)
    _post(client, _response(idp, in_response_to=request_id, email="fresh@corp.test", attributes={"Role": ["namifax-admin"]}))
    user = dbsession.execute(select(UserAccount).where(UserAccount.email == "fresh@corp.test")).scalar_one()
    assert user.is_admin and not user.superuser


def test_the_new_rights_work_in_the_same_session(client, mapping, person, idp):
    _login_with(client, idp, Role=["namifax-admin"])
    assert client.get("/admin").status_int == 200


def test_the_roles_are_only_believed_when_signed(client, mapping, person, idp, dbsession):
    request_id = _start(client)
    _post(client, _response(idp, in_response_to=request_id, sign=False, attributes={"Role": ["namifax-admin"]}))
    assert not _account(dbsession).is_admin


def test_the_admin_page_saves_the_mapping(client, mapping, dbsession):
    client.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    page = client.get("/admin/saml")
    form = next(f for f in page.forms.values() if "idp_sso_url" in f.fields)
    assert form["saml_role_attribute"].value == "Role" and form["saml_role_admin"].value == "namifax-admin"
    form["saml_role_admin"] = "fax-admins"
    form.submit()
    assert mapping.get("saml_role_admin") == "fax-admins"
