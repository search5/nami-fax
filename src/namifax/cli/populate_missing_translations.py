"""Populate missing translations across all locales and compile MO files."""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
from babel.messages import pofile

LOCALE_DIR = "src/namifax/locale"
SCRATCH_DIR = "scratch"


def populate():
    json_files = sorted(glob.glob(os.path.join(SCRATCH_DIR, "translations_*.json")))
    if not json_files:
        print("No translation JSON files found in scratch/.")
        return False

    updated_locales = []

    for jpath in json_files:
        fname = os.path.basename(jpath)
        lang = fname.replace("translations_", "").replace(".json", "")
        po_path = os.path.join(LOCALE_DIR, lang, "LC_MESSAGES", "namifax.po")
        if not os.path.exists(po_path):
            print(f"Skipping {lang}: {po_path} does not exist")
            continue

        with open(jpath, "r", encoding="utf-8") as f:
            trans_map = json.load(f)

        with open(po_path, "rb") as f:
            catalog = pofile.read_po(f)

        # Normalize keys in trans_map (handle escaped quotes)
        norm_map = {}
        for k, v in trans_map.items():
            norm_map[k] = v
            norm_map[k.replace('\\"', '"')] = v
            norm_map[k.replace('"', '\\"')] = v

        filled_count = 0
        for message in catalog:
            if not message.id:
                continue
            # if empty or untranslated
            if not message.string:
                mid = message.id
                if mid in norm_map and norm_map[mid]:
                    message.string = norm_map[mid]
                    filled_count += 1

        with open(po_path, "wb") as f:
            pofile.write_po(f, catalog, ignore_obsolete=False)

        updated_locales.append((lang, filled_count))
        print(f"[{lang}] Injected {filled_count} translations.")

    print("\nCompiling all catalogs to MO...")
    res = subprocess.run(
        [sys.executable, "-m", "babel.messages.frontend", "compile", "-d", LOCALE_DIR, "-D", "namifax"],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print(f"Compile failed: {res.stderr}")
        return False

    print("Compilation completed successfully.\n")

    # Verify statistics
    print("=== Verification Statistics ===")
    for lang in sorted(os.listdir(LOCALE_DIR)):
        po_path = os.path.join(LOCALE_DIR, lang, "LC_MESSAGES", "namifax.po")
        if not os.path.exists(po_path) or lang == "en":
            continue
        with open(po_path, "rb") as f:
            cat = pofile.read_po(f)
        total = len([m for m in cat if m.id])
        empty = len([m for m in cat if m.id and not m.string])
        translated = total - empty
        print(f"{lang:6s}: {translated}/{total} ({translated/total*100:.1f}%)")

    return True


if __name__ == "__main__":
    populate()
