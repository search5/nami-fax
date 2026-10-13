"""A browser that is sent from another site to a state-changing address is refused (cross-site request forgery).

Every POST (and PUT/PATCH/DELETE) is checked: when the request says where it came from (Origin, else Referer) that must be
this site. A request that says nothing (a script, a test) is not refused. The SAML callbacks are posted by the identity
provider from its own site, so they are exempt.
"""

from __future__ import annotations

import pytest

EVIL = {"Origin": "https://evil.test"}


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


@pytest.mark.parametrize("path,data", [
    ("/settings", {"name": "x"}),
    ("/ajax/archivefax", {"fids": "1"}),
    ("/admin/users", {"name": "n", "username": "u"}),
    ("/addressbook/edit", {"company": "x"}),
    ("/logout", {}),
])
def test_a_post_from_another_site_is_refused(client, path, data):
    assert client.post(path, data, headers=EVIL, expect_errors=True).status_int == 403


def test_the_referer_is_used_when_there_is_no_origin(client):
    res = client.post("/settings", {"name": "x"}, headers={"Referer": "https://evil.test/page"}, expect_errors=True)
    assert res.status_int == 403


def test_a_post_from_this_site_is_accepted(client):
    host = client.extra_environ["HTTP_HOST"]
    res = client.post("/ajax/archivefax", {"fids": "1"}, headers={"Origin": f"http://{host}"}, expect_errors=True)
    assert res.status_int != 403
    res = client.post("/ajax/archivefax", {"fids": "1"}, headers={"Referer": f"http://{host}/inbox"}, expect_errors=True)
    assert res.status_int != 403


def test_a_post_that_says_nothing_about_its_origin_is_accepted(client):
    assert client.post("/ajax/archivefax", {"fids": "1"}, expect_errors=True).status_int != 403


def test_the_origin_null_of_a_sandboxed_page_is_refused(client):
    assert client.post("/ajax/archivefax", {"fids": "1"}, headers={"Origin": "null"}, expect_errors=True).status_int == 403


def test_reading_pages_is_never_refused(client):
    assert client.get("/inbox", headers=EVIL).status_int == 200


def test_behind_a_proxy_the_forwarded_host_counts_as_this_site(client):
    res = client.post("/ajax/archivefax", {"fids": "1"},
                      headers={"Origin": "https://fax.corp.test", "X-Forwarded-Host": "fax.corp.test"}, expect_errors=True)
    assert res.status_int != 403


def test_a_listed_origin_is_accepted(dbengine):
    from namifax import create_app

    app = create_app(dbengine=dbengine, **{"csrf.trusted_origins": "https://fax.corp.test, https://other.corp.test"})
    import webtest

    client = webtest.TestApp(app, extra_environ={"HTTP_HOST": "internal:8000"})
    client.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    assert client.post("/ajax/archivefax", {"fids": "1"}, headers={"Origin": "https://fax.corp.test"}, expect_errors=True).status_int != 403
    assert client.post("/ajax/archivefax", {"fids": "1"}, headers={"Origin": "https://evil.test"}, expect_errors=True).status_int == 403


@pytest.mark.parametrize("path", ["/auth/saml/acs", "/auth/saml/sls"])
def test_the_identity_providers_callbacks_are_exempt(client, path):
    assert client.post(path, {"SAMLResponse": "x"}, headers=EVIL, expect_errors=True).status_int != 403
