"""LIKE pattern for the user-facing "search as you type" boxes."""

from __future__ import annotations

ESCAPE_CHAR = "!"


def like_pattern(text: str) -> str:
    """Pattern matching the words of ``text`` in order, anywhere in the value.

    ``"acm corp"`` becomes ``%acm%corp%``. Characters the user typed that mean something to LIKE
    (``%``, ``_`` and the escape character itself) are escaped, so they only match themselves.
    Use it with ``ESCAPE '!'``, which means the same on every database.
    """
    words = text.lower().split()
    escaped = [w.replace(ESCAPE_CHAR, ESCAPE_CHAR * 2).replace("%", ESCAPE_CHAR + "%").replace("_", ESCAPE_CHAR + "_")
               for w in words]
    return "%" + "%".join(escaped) + "%"


def like_patterns(text: str) -> list[str]:
    """``like_pattern`` for the text as typed and, when it differs, as the original AvantFAX stored such text (HTML entities:
    ``müller`` is ``m&uuml;ller`` in a database it wrote), so that a search finds both."""
    from namifax.models.types import legacy_encode

    patterns = [like_pattern(text)]
    encoded = like_pattern(legacy_encode(text))
    if encoded not in patterns:
        patterns.append(encoded)
    return patterns
