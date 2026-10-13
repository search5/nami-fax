"""FaxArchive queries on a SQLAlchemy session (portable across SQLite, MySQL, MariaDB and PostgreSQL).

These mirror the SQL that ``FaxPDFArchive`` builds for the legacy engine and are checked against it by a
differential test. Where the legacy SQL was not valid on every database it is replaced, not copied:
integer columns are never compared with ``''``, paging uses LIMIT/OFFSET (not MySQL's ``LIMIT a, b``) and
NULLs are ordered the same way everywhere.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, false, func, or_, select

from namifax.db.textsearch import ESCAPE_CHAR, like_pattern, like_patterns
from namifax.models.addressbook import AddressBookFAX
from namifax.models.faxarchive import FaxArchive as F


def _int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _eq_int(column: Any, value: Any) -> Any:
    """``column = value`` for an integer column; a value that is not a number matches nothing."""
    number = _int(value)
    return column == number if number is not None else false()


def routes_clause(column: Any, items: Any, numeric: bool) -> Optional[Any]:
    """OR of ``column = item``; None when there is nothing to match (same rule as the legacy builder)."""
    if items is None:
        return None
    if not isinstance(items, list):
        items = [items]
    clauses = [(_eq_int(column, x) if numeric else column == str(x)) for x in items if x is not None]
    return or_(*clauses) if clauses else None


def row_dict(row: Any) -> Dict[str, Any]:
    return {c.name: getattr(row, c.key) for c in F.__table__.columns}


# --- inbox ------------------------------------------------------------------------------------------------

def inbox_filters(devices: Optional[List[Any]], faxcats: Optional[List[Any]], enable_did_routing: bool) -> List[Any]:
    filters: List[Any] = []
    if devices is not None:
        routes = []
        for dev in devices if isinstance(devices, list) else []:
            if dev == "" or dev is None:
                continue
            routes.append(_eq_int(F.didr_id, dev) if enable_did_routing else F.modemdev == str(dev))
        filters.append(or_(*routes) if routes else F.modemdev == "")
    if isinstance(faxcats, list):
        cats = [_eq_int(F.faxcatid, c) for c in faxcats if c is not None]
        filters.append(or_(*cats, F.faxcatid.is_(None)))
    return filters


def count_inbox(session: Any, filters: List[Any]) -> int:
    return session.execute(select(func.count()).select_from(F).where(F.inbox == 1, *filters)).scalar_one()


def inbox_fids(session: Any, filters: List[Any]) -> List[int]:
    return list(session.execute(select(F.fid).where(F.inbox == 1, *filters).order_by(F.fid.desc())).scalars())


def list_inbox(session: Any, filters: List[Any], offset: int, limit: int, order_by_modem: bool) -> List[Dict[str, Any]]:
    order = [F.fid.desc()]
    if order_by_modem:
        order = [F.modemdev.is_(None).desc(), F.modemdev, F.fid.desc()]       # NULLs first, like the legacy order
    stmt = select(F).where(F.inbox == 1, *filters).order_by(*order).limit(limit).offset(offset)
    return [row_dict(r) for r in session.execute(stmt).scalars()]


def fids_older_than(session: Any, cutoff: str, inbox: Optional[int] = None) -> List[int]:
    stmt = select(F.fid).where(F.archstamp < cutoff)
    if inbox is not None:
        stmt = stmt.where(F.inbox == inbox)
    return list(session.execute(stmt.order_by(F.fid)).scalars())


# --- archive search -----------------------------------------------------------------------------------------

def _search_conditions(c: Dict[str, Any]) -> List[Any]:
    enable_did = c.get("enable_did_routing", False)
    restricted = c.get("restricted_user_mode", False)
    superuser = c.get("superuser", False)
    userid, category = c.get("userid"), c.get("category")
    sentrecvd = c.get("sentrecvd")

    didr = routes_clause(F.didr_id, c.get("didroutes"), True)
    cats = routes_clause(F.faxcatid, c.get("categories"), True)
    mdev = routes_clause(F.modemdev, c.get("modemdevs"), False)
    target = didr if enable_did else mdev
    by_user = _eq_int(F.userid, userid) if userid else false()
    combine = and_ if restricted else or_
    conds: List[Any] = [F.inbox == 0]

    def restrict(extra: Optional[Any] = None) -> None:
        """Limit to the user's routes/categories (the same shape for received and 'everything' searches)."""
        alt = [extra] if extra is not None else []
        if category:
            if target is not None:
                conds.append(or_(target, *alt))
        elif target is not None and cats is not None:
            conds.append(or_(combine(target, cats), and_(target, F.faxcatid.is_(None)), *alt))
        elif target is None and cats is not None:
            conds.append(or_(cats, *alt))
        elif target is not None and cats is None:
            conds.append(or_(target, *alt))
        else:
            # No modem/route and no category on the account. In the original an empty list still yields a condition
            # that nothing matches (``modemdev = ''``), so such an account sees only the faxes it sent itself.
            conds.append(or_(*alt) if alt else false())

    if sentrecvd == "s":
        conds.append(by_user if userid else F.userid.is_not(None))
        conds.append(F.modemdev.is_(None))
    elif sentrecvd == "r":
        if not superuser:
            restrict()
        else:
            conds.append(F.modemdev.is_not(None))
        if category:
            conds.append(_eq_int(F.faxcatid, category))
        conds.append(or_(F.userid == 0, F.userid.is_(None)))
    elif sentrecvd == "*":
        if not superuser:
            restrict(by_user)
        elif userid:
            conds.append(by_user)
        if category:
            conds.append(_eq_int(F.faxcatid, category))
    else:
        if not superuser:
            conds.append(or_(target if target is not None else false(), by_user))
        elif userid:
            conds.append(by_user)

    start, end = c.get("start_date"), c.get("end_date")
    if start and end:
        conds.append(and_(F.archstamp > str(start), F.archstamp < str(end)))
    elif start:
        conds.append(F.archstamp.startswith(str(start), autoescape=True))
    if c.get("faxid"):
        conds.append(_eq_int(F.fid, c["faxid"]))
    if c.get("keywords"):
        pattern = like_pattern(str(c["keywords"]))
        conds.append(or_(*[func.lower(F.description).like(p, escape=ESCAPE_CHAR) for p in like_patterns(str(c["keywords"]))],
                         func.lower(F.faxcontent).like(pattern, escape=ESCAPE_CHAR)))
    if c.get("companyid"):
        conds.append(or_(_eq_int(AddressBookFAX.abook_id, c["companyid"]), _eq_int(F.companyid, c["companyid"])))
    return conds


def search(session: Any, criteria: Dict[str, Any]) -> tuple[int, List[Dict[str, Any]]]:
    """Return (matching rows, the requested page as ``[{"fid": n}]``)."""
    pagelimit = criteria.get("pagelimit", 25)
    pageindex = criteria.get("pageindex", 0)
    base = (select(F.fid).outerjoin(AddressBookFAX, F.faxnumid == AddressBookFAX.abookfax_id)
            .where(*_search_conditions(criteria)))
    numrows = session.execute(select(func.count()).select_from(base.subquery())).scalar_one()

    numpages = math.ceil(numrows / pagelimit) if numrows > pagelimit else 0
    if pageindex > (numpages - 1):
        pageindex = max(0, numpages - 1)
    if pageindex < 0:
        pageindex = 0
    page = session.execute(base.order_by(F.fid.desc()).limit(pagelimit).offset(pageindex * pagelimit)).scalars()
    return numrows, [{"fid": fid} for fid in page]
