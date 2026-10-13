"""Signing out is a POST with the session's CSRF token (a link could be followed by any other page, which would sign the user
out of NamiFAX against their will)."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup


def _token(client, path="/inbox"):
    return BeautifulSoup(client.get(path).text, "html.parser").find("input", {"name": "csrf_token"})["value"]


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _signed_in(client):
    return client.get("/inbox", expect_errors=True).status_int == 200


@pytest.mark.parametrize("page", ["/inbox", "/admin"])
def test_the_logout_button_is_a_post_form_with_the_token(client, page):
    form = BeautifulSoup(client.get(page).text, "html.parser").find("form", {"action": "/logout"})
    assert form is not None and form["method"].lower() == "post" and form.find("input", {"name": "csrf_token"})["value"]
    assert 'href="/logout"' not in client.get(page).text


def test_a_post_with_the_token_signs_out(client):
    res = client.post("/logout", {"csrf_token": _token(client)})
    assert res.status_int == 302 and res.headers["Location"].endswith("/login") and not _signed_in(client)


def test_a_link_to_logout_does_not_sign_out_but_asks(client):
    res = client.get("/logout")
    assert res.status_int == 200 and 'action="/logout"' in res.text and _signed_in(client)


def test_the_confirmation_page_signs_out(client):
    form = client.get("/logout").forms[0]
    res = form.submit()
    assert res.status_int == 302 and not _signed_in(client)


@pytest.mark.parametrize("token", [None, "", "wrong"])
def test_a_post_without_a_good_token_does_not_sign_out(client, token):
    data = {} if token is None else {"csrf_token": token}
    assert client.post("/logout", data, expect_errors=True).status_int == 400 and _signed_in(client)
