"""File upload handling and sanitization layer replacing legacy FileUpload.php."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Sequence

FU_NO_FILE = 201
FU_INVALIDMIME = 202
FU_OVER_SIZE = 203
FU_INI_SIZE = 204
FU_FORM_SIZE = 205
FU_PARTIAL = 206
FU_NO_TMPDIR = 207
FU_CANT_WRITE = 208


class FileUpload:
    """Manages file upload constraints, MIME detection, sanitization, and moving."""

    def __init__(self, debug: bool = False) -> None:
        self.debug = debug
        self._mimelimit: list[str] = []
        self._sizelimit: int = 0
        self._file_size: int = 0
        self._filename: str = ""
        self._mimetype: str = ""
        self._tmpname: str = ""
        self._error: int | None = None

    def sanitize_filename(self, filename: str) -> str:
        """Strip directory traversal and replace unsafe characters."""
        base = os.path.basename(filename)
        # Replace characters other than alphanumeric, dots, hyphens, underscores
        cleaned = re.sub(r"[^\w\.-]", "_", base)
        return cleaned

    def limit_mimetype(self, mimetypes_list: Sequence[str] | str) -> None:
        """Set allowed MIME types."""
        if isinstance(mimetypes_list, str):
            self._mimelimit = [mimetypes_list]
        else:
            self._mimelimit = list(mimetypes_list)

    def limit_size(self, size: int) -> None:
        """Set maximum allowed file size in bytes (0 for unlimited)."""
        self._sizelimit = int(size)

    def load_file(self, file_info: dict[str, Any] | str | Path) -> bool:
        """Load and validate uploaded file dictionary or file path."""
        self._error = None

        if isinstance(file_info, (str, Path)):
            path = Path(file_info)
            if not path.exists():
                self._error = FU_NO_FILE
                return False
            raw_dict = {
                "name": path.name,
                "tmp_name": str(path),
                "size": path.stat().st_size,
                "type": mimetypes.guess_type(str(path))[0] or "application/octet-stream",
                "error": 0,
            }
        else:
            raw_dict = file_info

        error_code = raw_dict.get("error", 0)
        if error_code != 0:
            err_map = {
                1: FU_INI_SIZE,
                2: FU_FORM_SIZE,
                3: FU_PARTIAL,
                4: FU_NO_FILE,
                6: FU_NO_TMPDIR,
                7: FU_CANT_WRITE,
            }
            self._error = err_map.get(error_code, FU_NO_FILE)
            return False

        tmp_name = raw_dict.get("tmp_name", "")
        if not tmp_name or not os.path.exists(tmp_name):
            self._error = FU_NO_FILE
            return False

        self._tmpname = tmp_name
        self._filename = self.sanitize_filename(raw_dict.get("name", "upload.bin"))
        self._file_size = raw_dict.get("size", os.path.getsize(tmp_name))

        # Size check
        if self._sizelimit > 0 and self._file_size > self._sizelimit:
            self._error = FU_OVER_SIZE
            return False

        # Detect mimetype
        detected_mime = raw_dict.get("type")
        if not detected_mime or detected_mime == "application/octet-stream":
            guessed, _ = mimetypes.guess_type(self._filename)
            detected_mime = guessed or "application/octet-stream"

        # Clean trailing semicolon or space
        detected_mime = detected_mime.split(";")[0].split(" ")[0]
        self._mimetype = detected_mime

        # MIME whitelist check
        if self._mimelimit:
            if self._mimetype not in self._mimelimit:
                self._error = FU_INVALIDMIME
                return False

        return True

    def set_name(self, filename: str) -> None:
        """Explicitly override filename."""
        self._filename = self.sanitize_filename(filename)

    def set_randname(self, n: int = 9) -> str:
        """Prepend unique random hash prefix to avoid collision."""
        entropy = f"{time.time()}_{os.getpid()}_{self._filename}"
        rand_prefix = hashlib.md5(entropy.encode("utf-8")).hexdigest()[:n]
        self._filename = f"{rand_prefix}{self._filename}"
        return self._filename

    def get_tempname(self) -> str:
        return self._tmpname

    def get_name(self) -> str:
        return self._filename

    def get_mimetype(self) -> str:
        return self._mimetype

    def get_filesize(self) -> int:
        return self._file_size

    def get_error(self) -> int | None:
        return self._error

    def movefile(self, dest_dir: str | Path) -> bool:
        """Move uploaded file to destination directory."""
        dest_path = Path(dest_dir)
        try:
            if not dest_path.exists():
                dest_path.mkdir(parents=True, exist_ok=True, mode=0o770)
            target = dest_path / self._filename
            shutil.copy2(self._tmpname, target)
            return True
        except Exception:
            return False
