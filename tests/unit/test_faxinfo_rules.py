"""faxinfo like the original: a file that is not a fax is None (so the hook reports it as corrupted), an unknown sender becomes the
reserved number, a SIP suffix is cut from the caller id; without HylaFAX's faxinfo the TIFF itself is read."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from namifax.common.helpers import faxinfo
from namifax.services.addressbook import RESERVED_FAX_NUM


def _tiff(path, pages=2, sender=None):
    frames = [Image.new("1", (200, 300), color=1) for _ in range(pages)]
    extra = {"tiffinfo": {285: sender}} if sender else {}
    frames[0].save(path, save_all=True, append_images=frames[1:], format="TIFF", compression="group4", **extra)
    return str(path)


def _binary(text, code=0):
    import contextlib

    @contextlib.contextmanager
    def both():
        with patch("shutil.which", return_value="/usr/bin/faxinfo"), \
                patch("subprocess.run", return_value=MagicMock(returncode=code, stdout=text)):
            yield

    return both()


def test_a_file_that_is_not_a_fax_is_not_valid(tmp_path):
    bad = tmp_path / "x.tif"
    bad.write_bytes(b"this is not a tiff")
    assert faxinfo(str(bad)) is None


def test_a_missing_file_is_not_valid(tmp_path):
    assert faxinfo(str(tmp_path / "none.tif")) is None


def test_a_tiff_gives_its_pages_and_a_received_date(tmp_path):
    info = faxinfo(_tiff(tmp_path / "f.tif", pages=3))
    assert int(info["Pages"]) == 3 and info["Received"].count(":") == 4


def test_the_sender_comes_from_the_tiff_when_it_has_one(tmp_path):
    assert faxinfo(_tiff(tmp_path / "f.tif", sender="+1 555 0100"))["Sender"] == "+1 555 0100"


def test_without_a_sender_it_is_the_reserved_number_not_zeros(tmp_path):
    assert faxinfo(_tiff(tmp_path / "f.tif"))["Sender"] == RESERVED_FAX_NUM


def test_the_hylafax_output_is_parsed():
    out = "Sender: 5551234\nPages: 2\nReceived: 2026:10:01 10:05:09\nCallID1: 5559999@sip.example.com\nCallID2: Acme\n"
    with _binary(out), patch("os.path.exists", return_value=True):
        info = faxinfo("/f/fax.tif")
    assert info["Sender"] == "5551234" and info["Pages"] == "2" and info["CallID1"] == "5559999"


@pytest.mark.parametrize("sender", ["UNKNOWN", "unspecified", ""])
def test_an_unknown_sender_becomes_the_reserved_number(sender):
    out = f"Sender: {sender}\nPages: 1\nReceived: 2026:10:01 10:05:09\n"
    with _binary(out), patch("os.path.exists", return_value=True):
        assert faxinfo("/f/fax.tif")["Sender"] == RESERVED_FAX_NUM


def test_output_without_pages_is_not_valid():
    with _binary("Sender: 1\nReceived: 2026:10:01 10:05:09\n"), patch("os.path.exists", return_value=True):
        assert faxinfo("/f/fax.tif") is None
