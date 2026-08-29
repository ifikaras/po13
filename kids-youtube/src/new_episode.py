#!/usr/bin/env python3
"""Create a new episode folder from template."""

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "episodes" / "01_ta_zoa_tou_dasous"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("slug", help="Episode folder slug, e.g. 03_ta_noumera")
    parser.add_argument("--title", required=True)
    parser.add_argument("--id", required=True, help="Episode number like 03")
    args = parser.parse_args()

    dest = ROOT / "episodes" / args.slug
    if dest.exists():
        raise SystemExit(f"Already exists: {dest}")

    dest.mkdir(parents=True)
    (dest / "assets").mkdir()

    script = {
        "id": args.id,
        "title": args.title,
        "description": f"Νέο επεισόδιο: {args.title}",
        "tags": ["παιδικά", "εκπαιδευτικό", "ελληνικά"],
        "thumbnail_text": args.title,
        "scenes": [
            {
                "id": "intro",
                "image": "intro.png",
                "narration": f"Γεια σου! Σήμερα θα μάθουμε για: {args.title}!",
                "on_screen": args.title,
                "subtitle": "Μικροί Εξερευνητές",
            }
        ],
    }
    (dest / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Created {dest}")
    print("Next: add PNG images to assets/ and edit script.json")


if __name__ == "__main__":
    main()
