"""New-fax notification like the original: the unread count is on every page (not only the inbox), /ajax/inbox appends the user's sound
file ("3|beep.wav") when it exists, and the page polls for new faxes (30 s) and for modem status (20 s)."""

from __future__ import annotations

import re

import pytest
from sqlalchemy import update

from namifax.models import UserAccount
from test_fax_access_control import _login, world  # noqa: F401


def _badge(html):
    m = re.search(r'data-inbox-count[^>]*>\s*(\d+)\s*<', html)
    return int(m.group(1)) if m else None


def test_the_count_is_shown_on_pages_other_than_the_inbox(world):
    client = _login(world, "root")
    for path in ("/sendfax", "/archive", "/addressbook", "/settings"):
        assert _badge(client.get(path).text) == 3, path


def test_no_unread_faxes_means_no_badge(world):
    assert _badge(_login(world, "carl").get("/sendfax").text) is None


def test_the_count_alone_when_no_sound_is_chosen(world):
    assert _login(world, "alice").get("/ajax/inbox").text.strip() == "1"


def test_the_sound_file_follows_the_count_when_it_exists(world, tmp_path, monkeypatch):
    monkeypatch.setenv("AVANTFAX_AUDIO_DIR", str(tmp_path))
    (tmp_path / "beep.wav").write_bytes(b"RIFF")
    world.db.execute(update(UserAccount).where(UserAccount.username == "alice").values(audiofile="beep.wav"))
    world.db.flush()
    assert _login(world, "alice").get("/ajax/inbox").text.strip() == "1|beep.wav"


def test_a_sound_file_that_is_gone_is_not_announced(world, tmp_path, monkeypatch):
    monkeypatch.setenv("AVANTFAX_AUDIO_DIR", str(tmp_path))
    world.db.execute(update(UserAccount).where(UserAccount.username == "alice").values(audiofile="gone.wav"))
    world.db.flush()
    assert _login(world, "alice").get("/ajax/inbox").text.strip() == "1"


def test_a_path_in_the_sound_setting_is_cut_to_the_file_name(world, tmp_path, monkeypatch):
    monkeypatch.setenv("AVANTFAX_AUDIO_DIR", str(tmp_path))
    (tmp_path / "beep.wav").write_bytes(b"RIFF")
    world.db.execute(update(UserAccount).where(UserAccount.username == "alice").values(audiofile="../../etc/beep.wav"))
    world.db.flush()
    assert _login(world, "alice").get("/ajax/inbox").text.strip() == "1|beep.wav"


def test_the_sound_is_served_to_signed_in_users(world, tmp_path, monkeypatch):
    monkeypatch.setenv("AVANTFAX_AUDIO_DIR", str(tmp_path))
    (tmp_path / "beep.wav").write_bytes(b"RIFFdata")
    res = _login(world, "alice").get("/audio/beep.wav")
    assert res.body == b"RIFFdata" and res.content_type.startswith("audio/")
    assert _login(world, "alice").get("/audio/..%2Fsecret", expect_errors=True).status_int == 404
    assert _login(world, "alice").get("/audio/missing.wav", expect_errors=True).status_int == 404


def test_the_page_loads_the_poller_with_the_original_intervals(world):
    html = _login(world, "alice").get("/inbox").text
    assert "/static/js/notify.js" in html
    assert 'data-inbox-poll="30"' in html and 'data-modem-poll="20"' in html


def test_the_poller_script_is_served(world):
    res = _login(world, "alice").get("/static/js/notify.js")
    assert res.status_int == 200 and b"/ajax/inbox" in res.body and b"/ajax/modemstatus" in res.body
