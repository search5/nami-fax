"""What may be uploaded to be faxed (the original's FileUpload limits: PDF, PostScript, TIFF and plain text) and how big."""

from __future__ import annotations

import os
from typing import Optional

DEFAULT_MAX_BYTES = 10 * 1024 * 1024
HEAD = 4096

UNAUTHORIZED = "File type is unauthorized"
OVER_LIMIT = "File size is over the limit"


def max_bytes() -> int:
    raw = os.environ.get("NAMIFAX_MAX_UPLOAD_BYTES", "")
    return int(raw) if raw.isdecimal() and int(raw) > 0 else DEFAULT_MAX_BYTES


def max_label() -> str:
    return f"{max_bytes() / (1024 * 1024):g} MB"


def kind(head: bytes) -> Optional[str]:
    """pdf, ps, tiff or text by what the file starts with (not by its name); None for anything else."""
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"%!"):
        return "ps"
    if head[:4] in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
        return "tiff"
    if head and b"\x00" not in head:
        try:
            head.decode("utf-8")
        except UnicodeDecodeError:
            try:
                head[:-3].decode("utf-8")                    # the cut may fall inside a character
            except UnicodeDecodeError:
                return None
        return "text"
    return None


def check(head: bytes, size: int) -> Optional[str]:
    """An error message for a file that may not be sent, else None."""
    if size > max_bytes():
        return OVER_LIMIT
    return None if kind(head) else UNAUTHORIZED
