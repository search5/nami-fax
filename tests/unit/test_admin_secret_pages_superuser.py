"""SMTP, network printers, storage and SAML hold passwords, keys and certificates: the pages say "Superadmin permission required",
so an administrator who is not a superuser must be refused (it used to pass with ``is_admin`` alone)."""

from __future__ import annotations

import pytest

from namifax.services.user_account import NFUserAccount

PAGES = ["/admin/smtp", "/admin/printers", "/admin/storage", "/admin/saml"]


@pytest.fixture
def plain_admin(testapp, dbsession):
    acct = NFUserAccount(db=dbsession)
    assert acct.create({"username": "sub", "password": "Secret123!", "email": "sub@x.test", "name": "Sub", "is_admin": 1,
                        "superuser": 0, "acc_enabled": 1, "last_login": "2026-01-01 10:00:00"})
    dbsession.flush()
    res = testapp.post("/login", {"username": "sub", "password": "Secret123!", "_submit_check": "1"})
    assert res.status_int == 302
    return testapp


@pytest.fixture
def superuser(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


@pytest.mark.parametrize("path", PAGES)
def test_an_administrator_who_is_not_a_superuser_is_refused(plain_admin, path):
    assert plain_admin.get(path, expect_errors=True).status_int == 403


@pytest.mark.parametrize("path", PAGES)
def test_a_superuser_can_open_the_page(superuser, path):
    assert superuser.get(path).status_int == 200


@pytest.mark.parametrize("path", PAGES)
def test_a_non_superuser_cannot_post_either(plain_admin, path):
    res = plain_admin.post(path, {"action": "save_cloud", "storage_type": "S3", "bucket_name": "x"}, expect_errors=True)
    assert res.status_int == 403
