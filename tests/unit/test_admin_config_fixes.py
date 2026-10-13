"""Admin configuration pages as the original had them: modems (category, create/save/delete, messages), barcode routes with a
category, deleting a category frees its faxes, dynconf names modems by alias."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import select

from namifax.models import BarcodeRoute, FaxArchive, FaxCategory, Modems


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _form(page, field):
    return next(f for f in page.forms.values() if field in f.fields)


def _modem(session, device):
    session.expire_all()
    return session.execute(select(Modems).where(Modems.device == device)).scalar_one_or_none()


# --- modems -------------------------------------------------------------------------------------------------------------------

def test_the_modem_form_offers_the_categories(client):
    form = _form(client.get("/admin/modems"), "faxcatid")
    assert [v for v, _, _ in form["faxcatid"].options][0] == "" and len(form["faxcatid"].options) >= 2


def test_a_modem_is_created_with_its_category_and_the_page_says_so(client, dbsession):
    form = _form(client.get("/admin/modems"), "faxcatid")
    form["device"], form["alias"], form["faxcatid"] = "ttyUSB9", "USB line", "2"
    res = form.submit("create")
    assert "created" in res.text.lower()
    modem = _modem(dbsession, "ttyUSB9")
    assert modem.alias == "USB line" and modem.faxcatid == 2


def test_creating_an_existing_device_is_refused(client, dbsession):
    before = _modem(dbsession, "ttyS0").alias
    form = _form(client.get("/admin/modems"), "faxcatid")
    form["device"], form["alias"] = "ttyS0", "Changed"
    res = form.submit("create")
    assert "exist" in res.text.lower() and _modem(dbsession, "ttyS0").alias == before


@pytest.mark.parametrize("device,alias,text", [("", "Alias", "device"), ("ttyUSB8", "", "alias")])
def test_a_modem_needs_a_device_and_an_alias(client, dbsession, device, alias, text):
    form = _form(client.get("/admin/modems"), "faxcatid")
    form["device"], form["alias"] = device, alias
    res = form.submit("create")
    assert text in res.text.lower() and _modem(dbsession, "ttyUSB8") is None


def test_an_existing_modem_can_be_saved_or_deleted(client, dbsession):
    devid = _modem(dbsession, "ttyS1").devid
    page = client.get(f"/admin/modems?devid={devid}")
    form = _form(page, "faxcatid")
    assert "save" in form.fields and "delete" in form.fields and form["devid"].value == str(devid)
    form["alias"], form["faxcatid"] = "Renamed line", "3"
    res = form.submit("save")
    assert "updated" in res.text.lower()
    assert (_modem(dbsession, "ttyS1").alias, _modem(dbsession, "ttyS1").faxcatid) == ("Renamed line", 3)
    res = _form(client.get(f"/admin/modems?devid={devid}"), "faxcatid").submit("delete")
    assert "deleted" in res.text.lower() and _modem(dbsession, "ttyS1") is None


# --- barcode routes -----------------------------------------------------------------------------------------------------------

def test_a_barcode_route_keeps_its_category(client, dbsession):
    form = _form(client.get("/admin/barcodes"), "faxcatid")
    form["barcode"], form["alias"], form["faxcatid"] = "BC-4242", "Invoices desk", "2"
    form.submit("create")
    dbsession.expire_all()
    route = dbsession.execute(select(BarcodeRoute).where(BarcodeRoute.barcode == "BC-4242")).scalar_one()
    assert route.faxcatid == 2
    form = _form(client.get(f"/admin/barcodes?barcode_id={route.barcode_id}"), "faxcatid")
    assert form["faxcatid"].value == "2"
    form["faxcatid"] = "3"
    form.submit("save")
    dbsession.expire_all()
    assert dbsession.get(BarcodeRoute, route.barcode_id).faxcatid == 3


# --- categories ---------------------------------------------------------------------------------------------------------------

def test_deleting_a_category_frees_the_faxes_that_had_it(client, dbsession):
    category = FaxCategory(name="Temporary")
    dbsession.add(category)
    dbsession.flush()
    fax = FaxArchive(faxpath="/f/t", pages=1, inbox=1, faxcatid=category.catid)
    dbsession.add(fax)
    dbsession.flush()
    _form(client.get(f"/admin/categories?catid={category.catid}"), "name").submit("delete")
    dbsession.expire_all()
    assert dbsession.get(FaxArchive, fax.fid).faxcatid is None


# --- dynconf ------------------------------------------------------------------------------------------------------------------

def test_dynconf_names_a_modem_by_its_alias(client, dbsession):
    soup = BeautifulSoup(client.get("/admin/dynconf").text, "html.parser")
    labels = [o.get_text(strip=True) for o in soup.find("select", {"name": "device"}).find_all("option")]
    alias = _modem(dbsession, "ttyS0").alias
    assert any(alias in label and "ttyS0" in label for label in labels)
    assert "ttyS0" in [o["value"] for o in soup.find("select", {"name": "device"}).find_all("option")]
