"""Dashboard: the HylaFAX version is the one `faxstat -i` reports (not a fixed text) and each modem's colour follows its status class."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from namifax.services import hylafax_info


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def test_the_version_is_read_from_faxstat():
    out = "HylaFAX scheduler on host: Running\nServer status:\n    Server version: HylaFAX 6.0.7 built Jun 1 2023\n"
    with patch("shutil.which", return_value="/usr/bin/faxstat"), patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=out)):
        assert hylafax_info.version() == "6.0.7"


def test_another_output_shape_is_understood():
    out = "Modem info\nHylaFAX version 7.0.8 built on Tue\n"
    with patch("shutil.which", return_value="/usr/bin/faxstat"), patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=out)):
        assert hylafax_info.version() == "7.0.8"


def test_without_faxstat_the_version_is_unknown_not_invented():
    with patch("shutil.which", return_value=None):
        assert hylafax_info.version() is None


def test_the_dashboard_shows_the_found_version_or_says_unknown(client):
    with patch("namifax.views.admin.hylafax_info.version", return_value="9.9.9"):
        assert "9.9.9" in client.get("/admin").text
    with patch("namifax.views.admin.hylafax_info.version", return_value=None):
        html = client.get("/admin").text
    assert "6.0.7" not in html


@pytest.mark.parametrize("css,colour", [("modem-free", "emerald"), ("modem-send", "sky"), ("modem-recv", "indigo"), ("modem-wait", "amber")])
def test_a_modems_colour_follows_its_status_class(client, css, colour):
    fake = [{"devid": 1, "device": "ttyS0", "alias": "Main", "status": "x", "status_class": css}]
    with patch("namifax.views.admin.get_all_admin_modems", return_value=fake):
        html = client.get("/admin").text
    segment = html[html.index("modem-status-div"):]
    assert f"{colour}-" in segment.split("</div>")[0] or f"data-state=\"{css}\"" in segment
