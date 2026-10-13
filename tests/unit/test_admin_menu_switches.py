"""The admin menu hides DID routing and barcode routing unless the settings turn them on (like the original header.tpl)."""

from __future__ import annotations

import pytest


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _links(client):
    html = client.get("/admin/users").text
    return '"/admin/did"' in html, '"/admin/barcodes"' in html


def test_both_menus_are_hidden_by_default(client, monkeypatch):
    monkeypatch.delenv("ENABLE_DID_ROUTING", raising=False)
    monkeypatch.delenv("ENABLE_BARDECODE_SUPPORT", raising=False)
    assert _links(client) == (False, False)


def test_the_settings_show_them(client, monkeypatch):
    monkeypatch.setenv("ENABLE_DID_ROUTING", "1")
    monkeypatch.setenv("ENABLE_BARDECODE_SUPPORT", "true")
    assert _links(client) == (True, True)


def test_one_setting_shows_only_its_menu(client, monkeypatch):
    monkeypatch.setenv("ENABLE_DID_ROUTING", "1")
    monkeypatch.delenv("ENABLE_BARDECODE_SUPPORT", raising=False)
    assert _links(client) == (True, False)
