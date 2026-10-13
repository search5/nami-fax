"""Populate all 24 locales from legacy AvantFAX lang dictionaries and compiled MO files."""

from __future__ import annotations

import os
import re
from babel.messages import pofile, mofile

LANG_FILE_MAP: dict[str, str] = {
    "ar": "ar.php",
    "bg": "bg.php",
    "cs": "cz.php",
    "de": "de.php",
    "el": "el.php",
    "es": "es.php",
    "fr": "fr.php",
    "hu": "hu.php",
    "it": "it.php",
    "ja": "ja.php",
    "nl": "nl.php",
    "no": "no.php",
    "pl": "pl.php",
    "pt_BR": "pt-br.php",
    "pt_PT": "pt-pt.php",
    "ro": "ro.php",
    "ru": "ru.php",
    "sr": "rs.php",
    "sv": "sv.php",
    "tr": "tr.php",
    "zh_CN": "zh.php",
    "zh_TW": "zh-tw.php",
}


def parse_php_lang(path: str) -> dict[str, str]:
    d = {}
    if not os.path.exists(path):
        return d
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r"^\$LANG\[\x27([^\x27]+)\x27\]\s*=\s*\"(.*)\";", line.strip())
            if m:
                k, v = m.group(1), m.group(2)
                v = v.replace(r"\"", "\"").replace(r"\n", "\n")
                d[k] = v
    return d


def populate_all():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    langs_dir = os.path.join(root_dir, "legacy", "avantfax", "includes", "langs")
    locale_dir = os.path.join(root_dir, "src", "namifax", "locale")

    en_dict = parse_php_lang(os.path.join(langs_dir, "en.php"))

    # Build en_val -> [keys]
    en_val_to_keys: dict[str, list[str]] = {}
    for k, v in en_dict.items():
        v_clean = v.strip()
        en_val_to_keys.setdefault(v_clean, []).append(k)
        en_val_to_keys.setdefault(v_clean.lower(), []).append(k)

    for loc, php_file in LANG_FILE_MAP.items():
        php_path = os.path.join(langs_dir, php_file)
        tgt_dict = parse_php_lang(php_path)

        po_path = os.path.join(locale_dir, loc, "LC_MESSAGES", "namifax.po")
        mo_path = os.path.join(locale_dir, loc, "LC_MESSAGES", "namifax.mo")

        if not os.path.exists(po_path):
            continue

        with open(po_path, "rb") as f:
            catalog = pofile.read_po(f)

        updated = 0
        for msg in catalog:
            if not msg.id:
                continue
            msg_id_str = msg.id if isinstance(msg.id, str) else msg.id[0]

            # If already translated and not fuzzy, keep it
            if msg.string and "fuzzy" not in msg.flags:
                continue

            # Try matching with legacy en_dict
            keys = en_val_to_keys.get(msg_id_str.strip()) or en_val_to_keys.get(msg_id_str.strip().lower())
            if keys:
                for k in keys:
                    if k in tgt_dict and tgt_dict[k]:
                        msg.string = tgt_dict[k]
                        if "fuzzy" in msg.flags:
                            msg.flags.discard("fuzzy")
                        updated += 1
                        break

        with open(po_path, "wb") as f:
            pofile.write_po(f, catalog)

        with open(mo_path, "wb") as f:
            mofile.write_mo(f, catalog)

        print(f"[{loc}] Updated {updated} translations from {php_file}")

    # English keeps an empty msgstr, so the original English text of the source is shown as it is
    en_po = os.path.join(locale_dir, "en", "LC_MESSAGES", "namifax.po")
    en_mo = os.path.join(locale_dir, "en", "LC_MESSAGES", "namifax.mo")
    with open(en_po, "rb") as f:
        en_cat = pofile.read_po(f)
    for msg in en_cat:
        msg.string = ""
        if "fuzzy" in msg.flags:
            msg.flags.discard("fuzzy")
    with open(en_po, "wb") as f:
        pofile.write_po(f, en_cat)
    with open(en_mo, "wb") as f:
        mofile.write_mo(f, en_cat)
    print("[en] Verified original text fidelity (empty msgstr)")


if __name__ == "__main__":
    populate_all()
