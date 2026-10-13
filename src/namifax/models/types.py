"""Column types shared by the models."""

from __future__ import annotations

import re
from html.entities import codepoint2name, html5
from typing import Any

from datetime import date, datetime

from sqlalchemy import Boolean, String, Text
from sqlalchemy.types import TypeDecorator

_TRUE = {"1", "true", "t", "yes", "y", "on"}


class LegacyBoolean(TypeDecorator):
    """A boolean column that reads every spelling the old code wrote.

    The legacy engine used to store Python booleans as the *text* ``'False'``/``'True'``; a plain
    ``Boolean`` reads any non-empty text as true, so a ``'False'`` in ``superuser`` or ``is_admin`` would
    become a privilege. Reading is therefore done here, on the raw driver value, and unknown text is
    treated as false. DDL and writes are those of an ordinary ``Boolean`` (BOOLEAN / BOOL / BOOLEAN).
    """

    impl = Boolean
    cache_ok = True

    def process_result_value(self, value: Any, dialect: Any) -> bool | None:
        if value is None:
            return None
        if isinstance(value, (bool, int)):
            return bool(value)
        return str(value).strip().lower() in _TRUE

    def result_processor(self, dialect: Any, coltype: Any):
        # bypass the Boolean result processor, which would already have turned 'False' into True
        return lambda value: self.process_result_value(value, dialect)


class IsoText(TypeDecorator):
    """A date/time kept as ISO text (``YYYY-MM-DD HH:MM:SS`` / ``YYYY-MM-DD``) whatever the column is in the database.

    A database written by the original AvantFAX has real ``TIMESTAMP``/``DATE`` columns, which the driver reads as
    ``datetime``/``date`` objects; databases made by this application use ``VARCHAR``. The application works with ISO
    text everywhere (prefix searches, sorting, display), so values are converted on the way in and out.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, date):
            return value.isoformat()
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, date):
            return value.isoformat()
        return value


_ENTITY = re.compile(r"&(#[0-9]{1,7}|#[xX][0-9A-Fa-f]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});")


def _entity(match: "re.Match[str]") -> str:
    token = match.group(1)
    if token[0] == "#":
        number = int(token[2:], 16) if token[1] in "xX" else int(token[1:])
        return chr(number) if 0 < number <= 0x10FFFF and not 0xD800 <= number <= 0xDFFF else match.group(0)
    return html5.get(token + ";", match.group(0))


def legacy_decode(value: Any) -> Any:
    """Undo the HTML entities the original AvantFAX stored (it ran every form value through htmlentities, ENT_QUOTES, UTF-8).

    Only complete references (``&uuml;``, ``&#039;``, ``&#xFC;``) are undone, like PHP's html_entity_decode; ``html.unescape`` would
    also take ``&not`` out of ``&notice`` and the like."""
    if isinstance(value, str) and "&" in value:
        return _ENTITY.sub(_entity, value)
    return value


def legacy_encode(value: str) -> str:
    """What the original's htmlentities(ENT_QUOTES, "UTF-8") makes of ``value``, to search the text it stored.

    ``&``, ``<``, ``>``, ``"`` and the letters and signs that HTML 4 has a name for become named entities, ``'`` becomes ``&#039;``;
    anything else (Korean, Japanese, ...) is left as it is."""
    out = []
    for char in value:
        code = ord(char)
        if char == "'":
            out.append("&#039;")
        elif char in "&<>\"" or (code > 127 and code in codepoint2name):
            out.append(f"&{codepoint2name[code]};")
        else:
            out.append(char)
    return "".join(out)


class LegacyHtmlString(TypeDecorator):
    """Text a person typed. A database written by the original AvantFAX holds it as HTML entities; it is read as the text.

    It is a ``TypeDecorator`` and not a ``String`` subclass on purpose: a dialect that has its own string type (PostgreSQL's
    psycopg dialect does) replaces a subclass by its own class and the decoding is lost. Code that looks at the kind of a
    column has to look through it (``column.type.impl``)."""

    impl = String
    cache_ok = True

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        return legacy_decode(value)


class LegacyHtmlText(TypeDecorator):
    """``LegacyHtmlString`` for a ``TEXT`` column."""

    impl = Text
    cache_ok = True

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        return legacy_decode(value)
