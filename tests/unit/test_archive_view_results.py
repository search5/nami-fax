"""The archive search page must actually list what the search finds (it always came back empty)."""

from __future__ import annotations

import pytest
from pyramid import testing

from namifax.views.archive import archive_view
from request_identity import set_identity


WIDE = dict(kw="", sentrecvd="*", start_day="*", start_month="*", start_year="*", end_day="*", end_month="*", end_year="*")

pytestmark = pytest.mark.usefixtures("as_superuser")


def _request(dbsession, **params):
    req = testing.DummyRequest(params=params)
    set_identity(req, {"username": "admin", "uid": 1, "is_admin": True, "superuser": True})
    req.dbsession = dbsession
    req.db = dbsession
    return req


def test_search_lists_archived_faxes_with_company_and_details(dbsession):
    res = archive_view(_request(dbsession, **WIDE))
    assert [r["id"] for r in res["rows"]] == [2]                    # the seeded archived fax
    row = res["rows"][0]
    assert row["company"] == "Acme Corp"                                  # from the address book
    assert row["origfaxnum"] == "+1-555-0199" and row["pages"] == 2
    assert row["description"] == "Quarterly Financial Fax Transmission"
    assert row["archstamp"]


def test_search_by_keyword_and_fax_id(dbsession):
    assert [r["id"] for r in archive_view(_request(dbsession, **{**WIDE, "kw": "quarterly"}))["rows"]] == [2]
    assert archive_view(_request(dbsession, **{**WIDE, "kw": "no-such-text"}))["rows"] == []
    assert [r["id"] for r in archive_view(_request(dbsession, faxid="2", **WIDE))["rows"]] == [2]


def test_company_falls_back_to_the_fax_number_and_then_unknown(dbsession):
    from namifax.models import FaxArchive

    fax = dbsession.get(FaxArchive, 2)
    fax.companyid = None                     # still linked through the fax number (faxnumid=1)
    dbsession.flush()
    assert archive_view(_request(dbsession, **WIDE))["rows"][0]["company"] == "Acme Corp"
    fax.faxnumid = None
    dbsession.flush()
    assert archive_view(_request(dbsession, **WIDE))["rows"][0]["assign"] == "x"      # nobody knows the sender
