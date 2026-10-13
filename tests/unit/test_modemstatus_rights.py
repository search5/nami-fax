"""The modem status poller answers for the modems asked for (?modems=a,b) and only those the user may see; without a list, all of theirs."""

from __future__ import annotations

import re

from test_fax_access_control import _login, world  # noqa: F401


def _devices(res):
    return re.findall(r"<modem>([^<]*)</modem>", res.text)


def test_a_user_gets_only_their_own_modems(world):
    assert _devices(_login(world, "alice").get("/ajax/modemstatus")) == ["ttyS0"]
    assert _devices(_login(world, "bob").get("/ajax/modemstatus")) == ["ttyS1"]
    assert _devices(_login(world, "carl").get("/ajax/modemstatus")) == []


def test_a_modem_that_is_not_theirs_is_not_revealed_even_when_asked_for(world):
    assert _devices(_login(world, "alice").get("/ajax/modemstatus?modems=ttyS0,ttyS1")) == ["ttyS0"]
    assert _devices(_login(world, "alice").get("/ajax/modemstatus?modems=ttyS1")) == []


def test_the_list_asked_for_is_followed(world):
    assert _devices(_login(world, "root").get("/ajax/modemstatus?modems=ttyS1")) == ["ttyS1"]
    assert set(_devices(_login(world, "root").get("/ajax/modemstatus"))) >= {"ttyS0", "ttyS1"}


def test_an_unknown_modem_is_skipped(world):
    assert _devices(_login(world, "root").get("/ajax/modemstatus?modems=nope,ttyS0")) == ["ttyS0"]
