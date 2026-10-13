"""Admin > Storage: the connection fields belong to the chosen provider. Local storage needs none, and S3 / MinIO / Ceph need them;
(Google Cloud Storage is on hold: docs/ko/dev/gcs-on-hold.md) the page shows the fields that apply and follows the drop-down without reloading."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from namifax.services.system_config import SystemConfigService


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _page(client):
    return BeautifulSoup(client.get("/admin/storage").text, "html.parser")


def _hidden(node):
    return "hidden" in (node.get("class") or [])


def test_local_storage_shows_no_connection_fields(client, dbsession):
    SystemConfigService(dbsession).set("cloud_storage_type", "LOCAL")
    page = _page(client)
    fields = page.find(id="cloud-fields")
    assert fields is not None and _hidden(fields)
    assert page.find(id="cloud-note-LOCAL") is not None and not _hidden(page.find(id="cloud-note-LOCAL"))
    assert _hidden(page.find(id="cloud-test"))                                    # nothing to test for local files


def test_s3_shows_the_connection_fields(client, dbsession):
    SystemConfigService(dbsession).set("cloud_storage_type", "S3")
    page = _page(client)
    assert not _hidden(page.find(id="cloud-fields")) and not _hidden(page.find(id="cloud-test"))
    assert _hidden(page.find(id="cloud-note-LOCAL"))


def test_google_cloud_storage_is_not_offered(client):
    page = _page(client)
    assert [o["value"] for o in page.find("select", {"name": "storage_type"}).find_all("option")] == ["LOCAL", "S3"]
    assert b"GCS" not in client.get("/admin/storage").body


def test_the_dropdown_drives_the_fields(client):
    page = _page(client)
    select = page.find("select", {"name": "storage_type"})
    assert select["data-provider-switch"] == "cloud-fields"
    assert b"data-provider-switch" in client.get("/static/js/storage.js").body
    assert any(s.get("src") == "/static/js/storage.js" for s in page.find_all("script"))


def test_the_fields_still_post_with_the_form(client):
    form = next(f for f in client.get("/admin/storage").forms.values() if "storage_type" in f.fields)
    for name in ("endpoint_url", "region_name", "bucket_name", "access_key", "secret_key", "prefix"):
        assert name in form.fields, name
