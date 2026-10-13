"""Two-factor setup: the key can be copied with a button, the recovery codes can be copied and saved as a text file together with the
key. The file is made in the browser from what the page shows once; nothing is stored in clear and there is no endpoint that hands
the codes out again."""

from __future__ import annotations

import re

import pyotp
import pytest
from bs4 import BeautifulSoup
from sqlalchemy import select

from namifax.models import UserTOTP
from test_totp_enrollment import _login, _setup, _token  # noqa: F401


@pytest.fixture
def client(testapp):
    _login(testapp)
    return testapp


def test_the_setup_page_has_a_button_to_copy_the_key(client):
    page, secret, _t = _setup(client)
    soup = BeautifulSoup(page.text, "html.parser")
    button = soup.find("button", attrs={"data-copy": True})
    assert button is not None and button["data-copy"] == secret and button["type"] == "button"


def test_the_codes_page_can_copy_and_download(client):
    page, secret, token = _setup(client)
    done = client.post("/settings/2fa/enable", {"csrf_token": token, "code": pyotp.TOTP(secret).now()})
    soup = BeautifulSoup(done.text, "html.parser")
    codes = list(dict.fromkeys(re.findall(r"\b[A-Z2-9]{5}-[A-Z2-9]{5}\b", done.text)))
    assert len(codes) == 8
    copy = soup.find("button", attrs={"data-copy": True})
    assert copy["data-copy"].split("\n") == codes
    download = soup.find("button", attrs={"data-download": True})
    assert download["data-filename"].startswith("namifax-2fa-") and download["data-filename"].endswith(".txt")
    content = download["data-download"]
    assert all(c in content for c in codes) and secret not in content    # every code, and never the authenticator key


def test_recovery_codes_are_only_stored_as_hashes(client, dbsession):
    page, secret, token = _setup(client)
    done = client.post("/settings/2fa/enable", {"csrf_token": token, "code": pyotp.TOTP(secret).now()})
    codes = list(dict.fromkeys(re.findall(r"\b[A-Z2-9]{5}-[A-Z2-9]{5}\b", done.text)))
    stored = dbsession.execute(select(UserTOTP.backup_codes)).scalars().first()
    assert stored and not any(c in stored or c.replace("-", "") in stored for c in codes)
    assert secret not in (dbsession.execute(select(UserTOTP.secret_key)).scalars().first() or "")      # the key is encrypted


def test_regenerated_codes_can_be_saved_too_without_the_key(client):
    page, secret, token = _setup(client)
    client.post("/settings/2fa/enable", {"csrf_token": token, "code": pyotp.TOTP(secret).now()})
    form = next(f for f in client.get("/settings").forms.values() if f.action.endswith("/settings/2fa/recovery"))
    for name in form.fields:
        if name == "code":
            form["code"] = pyotp.TOTP(secret).now()
    res = form.submit()
    soup = BeautifulSoup(res.text, "html.parser")
    download = soup.find("button", attrs={"data-download": True})
    assert download is not None and secret not in download["data-download"] and "Recovery codes" in download["data-download"]
