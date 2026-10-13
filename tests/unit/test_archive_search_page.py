"""The archive page as the original archive.php: today's faxes until a search is made, filters (keyword, category by id, user for a
superuser, start/end day-month-year, sent/received), page size from the user, numbered rows and the row actions."""

from __future__ import annotations

import re
from datetime import date

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import update

from namifax.models import FaxArchive, FaxCategory, UserAccount
from test_fax_access_control import _fax, _login, world  # noqa: F401

TODAY = date.today().strftime("%Y-%m-%d")


@pytest.fixture
def arch(world, tmp_path):
    """Archived faxes: root sees all. R1 received today, R2 received 2025-06-15 (invoice), R3 received 2024-01-02, S sent by alice."""
    db = world.db
    db.execute(FaxArchive.__table__.delete())
    cat = FaxCategory(name="Invoices-x")
    db.add(cat)
    db.flush()
    world.cat = cat.catid

    def make(name, stamp, **kw):
        fid = _fax(db, tmp_path, f"arch_{name}", inbox=0, **kw)
        db.execute(update(FaxArchive).where(FaxArchive.fid == fid).values(archstamp=stamp, description=f"{name} text"))
        return fid

    world.fax = {
        "R1": make("R1", f"{TODAY} 09:00:00", modemdev="ttyS0"),
        "R2": make("R2", "2025-06-15 10:00:00", modemdev="ttyS0", faxcatid=cat.catid),
        "R3": make("R3", "2024-01-02 11:00:00", modemdev="ttyS1"),
        "S": make("S", "2025-06-20 12:00:00", userid=world.ids["alice"]),
    }
    db.flush()
    return world


def _get(arch, query="", user="root"):
    res = _login(arch, user).get("/archive" + query)
    soup = BeautifulSoup(res.text, "html.parser")
    ids = [int(r["id"].split("_")[1]) for r in soup.select("tr[id^=faxid_]")]
    return soup, ids


def _fids(arch, *names):
    return sorted(arch.fax[n] for n in names)


def test_without_a_search_only_todays_faxes_are_listed(arch):
    _, ids = _get(arch)
    assert ids == [arch.fax["R1"]]


def test_a_search_with_no_conditions_lists_them_all(arch):
    _, ids = _get(arch, "?kw=&sentrecvd=*&start_day=*&start_month=*&start_year=*&end_day=*&end_month=*&end_year=*")
    assert sorted(ids) == _fids(arch, "R1", "R2", "R3", "S")


def test_the_keyword_filters_the_description(arch):
    _, ids = _get(arch, "?kw=R2&sentrecvd=*&start_year=*&start_month=*&start_day=*&end_year=*&end_month=*&end_day=*")
    assert ids == [arch.fax["R2"]]


def test_the_category_filter_uses_the_category_id(arch):
    soup, ids = _get(arch, f"?kw=&category={arch.cat}&sentrecvd=*&start_year=*&start_month=*&start_day=*&end_year=*&end_month=*&end_day=*")
    assert ids == [arch.fax["R2"]]
    assert soup.find("select", {"name": "category"}).find("option", selected=True)["value"] == str(arch.cat)


def test_received_and_sent_values_are_the_originals(arch):
    soup, _ = _get(arch)
    values = [o["value"] for o in soup.find("select", {"name": "sentrecvd"}).find_all("option")]
    assert values == ["*", "s", "r"]
    wide = "&start_year=*&start_month=*&start_day=*&end_year=*&end_month=*&end_day=*&kw="
    assert _get(arch, "?sentrecvd=r" + wide)[1] == sorted(_fids(arch, "R1", "R2", "R3"), reverse=True)
    assert _get(arch, "?sentrecvd=s" + wide)[1] == [arch.fax["S"]]


def test_a_range_of_dates_uses_day_month_and_year(arch):
    query = "?kw=&sentrecvd=*&start_day=1&start_month=6&start_year=2025&end_day=30&end_month=6&end_year=2025"
    assert sorted(_get(arch, query)[1]) == _fids(arch, "R2", "S")
    query = "?kw=&sentrecvd=*&start_day=*&start_month=*&start_year=2024&end_day=*&end_month=*&end_year=2024"
    assert _get(arch, query)[1] == [arch.fax["R3"]]


def test_the_date_selects_are_lists_not_free_text(arch):
    soup, _ = _get(arch)
    for name in ("start_day", "start_month", "start_year", "end_day", "end_month", "end_year"):
        assert soup.find("select", {"name": name}) is not None, name
    months = [o.get_text(strip=True) for o in soup.find("select", {"name": "start_month"}).find_all("option")]
    assert months[:3] == ["", "January", "February"]
    today = date.today()
    assert soup.find("select", {"name": "start_day"}).find("option", selected=True)["value"] in (str(today.day), f"{today.day:02d}")


def test_only_a_superuser_can_filter_by_user(arch):
    soup, _ = _get(arch)
    assert soup.find("select", {"name": "userid"}) is not None
    assert _get(arch, user="alice")[0].find("select", {"name": "userid"}) is None
    wide = "?kw=&sentrecvd=*&start_year=*&start_month=*&start_day=*&end_year=*&end_month=*&end_day=*"
    assert _get(arch, wide + f"&userid={arch.ids['alice']}")[1] == [arch.fax["S"]]


def test_a_user_only_finds_what_they_may_see(arch):
    wide = "?kw=&sentrecvd=*&start_year=*&start_month=*&start_day=*&end_year=*&end_month=*&end_day=*"
    assert sorted(_get(arch, wide, user="alice")[1]) == _fids(arch, "R1", "R2", "S")   # her modem (or a category of hers) + her own sent


def test_the_category_list_of_a_user_is_their_own(arch):
    soup, _ = _get(arch, user="alice")
    values = [o["value"] for o in soup.find("select", {"name": "category"}).find_all("option")]
    assert str(arch.cat) not in values


def test_paging_uses_the_users_archive_page_size_and_numbers_the_rows(arch):
    arch.db.execute(update(UserAccount).where(UserAccount.username == "root").values(faxperpagearchive=10))
    for i in range(14):
        _fax(arch.db, __import__("pathlib").Path(arch.db.info.setdefault("t2", __import__("tempfile").mkdtemp())), f"arch_P{i}", inbox=0, modemdev="ttyS0")
    wide = "?kw=&sentrecvd=*&start_year=*&start_month=*&start_day=*&end_year=*&end_month=*&end_day=*"
    soup1, ids1 = _get(arch, wide)
    soup2, ids2 = _get(arch, wide + "&pageindex=1")
    assert len(ids1) == 10 and len(ids2) == 8 and not set(ids1) & set(ids2)
    assert "Total 18 results found." in soup1.get_text(" ", strip=True)
    first_numbers = [td.get_text(strip=True) for td in soup2.select("tr[id^=faxid_] td.archive-results:first-child")]
    assert first_numbers[0] == "11"
    hrefs = [a["href"] for a in soup2.select("nav.paging a")]
    assert any("pageindex=0" in h and "kw=" in h for h in hrefs)           # links keep the search


def test_a_row_shows_category_user_direction_and_actions(arch):
    wide = f"?kw=R2&sentrecvd=*&start_year=*&start_month=*&start_day=*&end_year=*&end_month=*&end_day=*"
    soup, _ = _get(arch, wide)
    row = soup.select_one("tr[id^=faxid_]")
    text = row.get_text(" ", strip=True)
    assert "Invoices-x" in text and "2025-06-15" in text
    hrefs = " ".join(a["href"] for a in row.find_all("a"))
    fid = arch.fax["R2"]
    for needle in (f"/faxes/download/{fid}?format=pdf", f"/refax?fid={fid}", f"/email?fid={fid}", f"/note?fid={fid}"):
        assert needle in hrefs or needle in str(row), needle
    assert f"/delete?fid={fid}" in str(row)                                  # root may delete


def test_a_user_who_cannot_delete_gets_no_delete_action(arch):
    wide = "?kw=R1&sentrecvd=*&start_year=*&start_month=*&start_day=*&end_year=*&end_month=*&end_day=*"
    soup, _ = _get(arch, wide, user="alice")
    assert "delete" not in str(soup.select_one("tr[id^=faxid_]")).lower()


def test_no_results_say_so(arch):
    soup, ids = _get(arch, "?kw=zzzz&sentrecvd=*&start_year=*&start_month=*&start_day=*&end_year=*&end_month=*&end_day=*")
    assert ids == [] and "No results were found" in soup.get_text(" ", strip=True)


# --- OpenSearch (the browser's search box) -----------------------------------------------------------------------------------

def test_the_site_describes_itself_for_browser_search(client_for_opensearch):
    res = client_for_opensearch.get("/search")
    assert res.content_type == "application/opensearchdescription+xml"
    assert "{searchTerms}" in res.text and "/archive?opensearch&amp;kw=" in res.text
    assert 'rel="search"' in client_for_opensearch.get("/inbox").text


def test_an_opensearch_query_looks_through_every_date(arch):
    _, ids = _get(arch, "?opensearch&kw=R3")                          # R3 is from 2024; "today" would never find it
    assert ids == [arch.fax["R3"]]


@pytest.fixture
def client_for_opensearch(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp
