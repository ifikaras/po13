#!/usr/bin/env python3
"""Create a new episode folder from template."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("slug", help="Episode folder slug, e.g. 03_numbers")
    parser.add_argument("--title", required=True, help="Short title, e.g. 'Numbers for Kids'")
    parser.add_argument("--id", required=True, help="Episode number like 03")
    parser.add_argument(
        "--youtube-title",
        help="Full SEO YouTube title (defaults to '<title> | Learn for Toddlers & Preschool')",
    )
    args = parser.parse_args()

    dest = ROOT / "episodes" / args.slug
    if dest.exists():
        raise SystemExit(f"Already exists: {dest}")

    dest.mkdir(parents=True)
    (dest / "assets").mkdir()

    yt_title = args.youtube_title or f"{args.title} | Learn for Toddlers & Preschool"
    slug_topic = args.title.lower().replace(" for kids", "")

    script = {
        "id": args.id,
        "title": args.title,
        "youtube_title": yt_title,
        "description": f"Learn {slug_topic} for kids! A fun and simple video for toddlers and preschoolers.",
        "tags": [
            f"{slug_topic} for kids",
            "learn for toddlers",
            "preschool learning",
            "kids educational video",
            "toddler learning",
            "kindergarten",
        ],
        "thumbnail_text": args.title,
        "scenes": [
            {
                "id": "intro",
                "image": "intro.png",
                "narration": f"Hello, little friend! Today we will learn about {slug_topic}! Are you ready? Let's go!",
                "on_screen": args.title,
                "subtitle": "Happy Little Learners",
            }
        ],
    }
    (dest / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Created {dest}")
    print("Next: add PNG images to assets/ and edit script.json")


if __name__ == "__main__":
    main()
