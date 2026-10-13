"""The Korean catalog has a translation for every message, and keeps the placeholders of the English text."""

from __future__ import annotations

import re
from pathlib import Path

from babel.messages import pofile

LOCALE = Path(__file__).resolve().parents[2] / "src" / "namifax" / "locale"
PLACEHOLDER = re.compile(r"%\([a-z_]+\)[sd]|%[sd]")


def _catalog(path):
    with open(path, "rb") as handle:
        return pofile.read_po(handle)


def test_every_message_of_the_template_is_translated_into_korean():
    ko = _catalog(LOCALE / "ko" / "LC_MESSAGES" / "namifax.po")
    pot_ids = [m.id for m in _catalog(LOCALE / "namifax.pot") if m.id]
    translated = {m.id for m in ko if m.id and m.string and "fuzzy" not in m.flags}
    missing = [i for i in pot_ids if i not in translated]
    assert missing == [], f"{len(missing)} messages without a Korean translation, e.g. {missing[:5]}"


def test_translations_keep_the_placeholders_of_the_original_text():
    ko = _catalog(LOCALE / "ko" / "LC_MESSAGES" / "namifax.po")
    broken = [m.id for m in ko if m.id and m.string and sorted(PLACEHOLDER.findall(m.id)) != sorted(PLACEHOLDER.findall(m.string))]
    assert broken == [], broken


def test_the_compiled_catalog_has_the_new_texts():
    from babel.support import Translations

    with open(LOCALE / "ko" / "LC_MESSAGES" / "namifax.mo", "rb") as handle:
        translations = Translations(handle, domain="namifax")
    assert translations.gettext("Send Password") == "비밀번호 보내기"
    assert translations.gettext("Schedule Send Time") == "전송 시각 예약"
