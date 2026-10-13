"""Nothing but the login-related pages may be used without signing in (every route is requested anonymously)."""

from __future__ import annotations

import pytest
import webtest

# routes that are public on purpose: they are how a person signs in
PUBLIC = {"home", "login", "logout", "forgot", "pwdexpired", "login_totp", "saml_metadata", "saml_login", "saml_acs",
          "saml_sls", "api_webauthn_auth_options", "api_webauthn_auth_verify"}


def _routes(app):
    from pyramid.interfaces import IRoutesMapper

    mapper = app.registry.getUtility(IRoutesMapper)
    return [(r.name, r.pattern) for r in mapper.get_routes() if r.name not in PUBLIC]


def _url(pattern):
    import re

    return re.sub(r"\{[^}]+\}", "1", pattern)


@pytest.fixture
def anonymous(app):
    return webtest.TestApp(app, extra_environ={"HTTP_HOST": "example.com"}), app


def test_every_route_needs_a_login(anonymous):
    client, app = anonymous
    open_routes = []
    for name, pattern in _routes(app):
        if name.startswith("__static") or pattern.startswith("static"):
            continue
        url = _url(pattern)
        for method in ("get", "post"):
            res = getattr(client, method)(url, {"_submit_check": "1"} if method == "post" else None, expect_errors=True)
            if res.status_int == 200:
                open_routes.append((method.upper(), url))
    # the OpenSearch description is public by design: a browser reads it without a session and it names nothing private
    assert open_routes == [("GET", "/search")]


def test_the_state_changing_ajax_calls_do_nothing_without_a_login(anonymous, dbsession):
    from sqlalchemy import select

    from namifax.models import FaxArchive

    client, _ = anonymous
    before = [f.fid for f in dbsession.execute(select(FaxArchive)).scalars()]
    assert before
    client.post("/ajax/deletefaxes", {"fids": ",".join(str(f) for f in before)}, expect_errors=True)
    client.post("/ajax/archivefax", {"fid": str(before[0])}, expect_errors=True)
    dbsession.expire_all()
    assert [f.fid for f in dbsession.execute(select(FaxArchive)).scalars()] == before
    assert dbsession.get(FaxArchive, before[0]).inbox in (0, 1) and dbsession.get(FaxArchive, before[0]).inbox == 1


def test_contact_lists_and_uploads_are_not_public(anonymous):
    client, _ = anonymous
    for path in ("/helper/emailcontacts", "/helper/faxcontacts", "/helper/distrocontacts", "/helper/distrolist",
                 "/ajax/book?q=a", "/ajax/emailbook?q=a", "/ajax/archivebook?q=a", "/upload/contacts", "/upload/faxcontacts"):
        assert client.get(path, expect_errors=True).status_int != 200, path


def test_signed_in_users_still_reach_them(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    for path in ("/helper/emailcontacts", "/helper/faxcontacts", "/ajax/book?q=a", "/ajax/inbox", "/upload/contacts"):
        assert testapp.get(path, expect_errors=True).status_int == 200, path
