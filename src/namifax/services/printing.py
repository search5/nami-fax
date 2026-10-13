"""Printing a received fax (the original faxrcvd's PRINTING SUPPORT).

The TIFF goes through ``fax2ps`` to ``lpr``, or - with FAXRCVD_PRINT_PDF - the PDF goes straight to the print command. The
programs are run without a shell, so a printer name is only ever an argument.
"""

from __future__ import annotations

import os
import subprocess

TRUE = ("1", "true", "True", "yes")


def _flag(name: str) -> bool:
    return os.environ.get(name, "0") in TRUE


def enabled() -> bool:
    return _flag("PRINTFAXRCVD")


def print_received(tiff_file: str, pdf_file: str, printer: str) -> bool:
    """Print the fax on ``printer`` (empty = the default printer). Returns whether the print command was accepted."""
    if not enabled():
        return False
    destination = ["-P", printer] if printer else []
    try:
        if _flag("FAXRCVD_PRINT_PDF"):
            result = subprocess.run([os.environ.get("PDFPRINTCMD", "/usr/bin/lpr"), *destination, pdf_file], check=False)
            return result.returncode == 0
        convert = subprocess.Popen([os.environ.get("PRINTFAX2PS", "/usr/bin/fax2ps"), tiff_file], stdout=subprocess.PIPE)
        spool = subprocess.Popen([os.environ.get("PRINTCMD", "/usr/bin/lpr"), *destination], stdin=convert.stdout)
        convert.wait()
        return spool.wait() == 0
    except OSError:
        return False
