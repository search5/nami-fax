"""Admin > System Logs like the original: with no search the day's events are listed; the chosen filter stays selected."""

from __future__ import annotations

from datetime import date

import pytest
from bs4 import BeautifulSoup

from namifax.services.syslog import SysLogService


@pytest.fixture
def client(testapp, dbsession):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    today = date.today().strftime("%Y-%m-%d")
    svc = SysLogService(dbsession)
    svc.add("event of today", f"{today} 08:00:00")
    svc.add("event of 2019", "2019-03-04 09:00:00")
    return testapp


def _texts(res):
    return [td.get_text(strip=True) for td in BeautifulSoup(res.text, "html.parser").select("tbody td") if td.get_text(strip=True)]


def test_without_a_search_only_todays_events_are_listed(client):
    texts = _texts(client.get("/admin/system_logs"))
    assert any("event of today" in t for t in texts) and not any("event of 2019" in t for t in texts)


def test_the_form_starts_on_today(client):
    soup = BeautifulSoup(client.get("/admin/system_logs").text, "html.parser")
    today = date.today()
    chosen = {n: soup.find("select", {"name": n}).find("option", selected=True) for n in ("day", "month", "year")}
    assert (int(chosen["day"]["value"]), int(chosen["month"]["value"]), int(chosen["year"]["value"])) == (today.day, today.month, today.year)


def test_a_search_for_a_year_finds_old_events_and_keeps_the_choice(client):
    res = client.get("/admin/system_logs?kw=event&day=&month=&year=2019&_submit_check=1")
    texts = _texts(res)
    assert any("event of 2019" in t for t in texts) and not any("event of today" in t for t in texts)
    soup = BeautifulSoup(res.text, "html.parser")
    assert soup.find("select", {"name": "year"}).find("option", selected=True)["value"] == "2019"
    assert soup.find("input", {"name": "kw"})["value"] == "event"


def test_the_years_reach_from_the_first_release_to_next_year(client):
    soup = BeautifulSoup(client.get("/admin/system_logs").text, "html.parser")
    values = [o["value"] for o in soup.find("select", {"name": "year"}).find_all("option") if o["value"]]
    assert values[0] == "2004" and values[-1] == str(date.today().year + 1)


def test_a_long_log_is_paged_and_every_page_is_reachable(client, dbsession):
    """C8: a filter with more than one page of events shows a pager; walking the pages shows every event once."""
    from namifax.views.admin import SYSLOG_PER_PAGE

    svc = SysLogService(dbsession)
    total = SYSLOG_PER_PAGE * 2 + 7
    for n in range(total):
        svc.add(f"bulk event {n:04d}", f"2018-05-06 10:{n // 60:02d}:{n % 60:02d}")
    seen = []
    for page in (1, 2, 3):
        res = client.get(f"/admin/system_logs?_submit_check=1&kw=bulk+event&year=2018&page={page}")
        seen += [t for t in _texts(res) if t.startswith("bulk event")]
        pager = BeautifulSoup(res.text, "html.parser").select_one("nav[aria-label=pager]")
        assert pager is not None and f"{page} / 3" in pager.get_text()
        assert "kw=bulk+event" in str(pager) and "year=2018" in str(pager)
    assert len(seen) == total == len(set(seen))
    assert seen[0] == f"bulk event {total - 1:04d}"


def test_a_short_log_has_no_pager_and_a_bad_page_number_is_the_first(client):
    res = client.get("/admin/system_logs?_submit_check=1&kw=event&year=2019&page=zzz")
    assert BeautifulSoup(res.text, "html.parser").select_one("nav[aria-label=pager]") is None
    assert any("event of 2019" in t for t in _texts(res))
    res = client.get("/admin/system_logs?_submit_check=1&kw=event&year=2019&page=99")
    assert any("event of 2019" in t for t in _texts(res))                     # beyond the end: the last page
