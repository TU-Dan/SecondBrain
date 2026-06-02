#!/usr/bin/env python3
"""Import episodes from a remote RSS feed into local podcast metadata."""

from __future__ import annotations

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from curl_cffi import requests


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from services.rss import generate_rss, load_episodes, save_episodes


def import_from_rss(rss_url: str, local_base_url: str) -> tuple[int, int]:
    """Import episodes from a remote RSS feed into local episodes.json."""
    resp = requests.get(rss_url, timeout=15, impersonate="chrome")
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("Invalid RSS: no <channel> found")

    existing = load_episodes()
    existing_urls = {ep["audio_url"] for ep in existing}
    imported = 0
    skipped = 0
    new_episodes = []

    for item in channel.findall("item"):
        enclosure = item.find("enclosure")
        if enclosure is None:
            continue

        audio_url = enclosure.get("url", "")
        if not audio_url:
            continue
        if audio_url in existing_urls:
            skipped += 1
            continue

        pub_date = item.findtext("pubDate", default="")
        try:
            published = parsedate_to_datetime(pub_date).isoformat()
        except Exception:
            published = datetime.now(timezone.utc).isoformat()

        new_episodes.append(
            {
                "title": item.findtext("title", default="Untitled"),
                "description": item.findtext("description", default=""),
                "audio_url": audio_url,
                "audio_length": int(enclosure.get("length", 0)),
                "published": published,
            }
        )
        existing_urls.add(audio_url)
        imported += 1

    if new_episodes:
        merged = new_episodes + existing
        merged.sort(key=lambda x: x["published"], reverse=True)
        save_episodes(merged)
        generate_rss(local_base_url)

    return imported, skipped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import remote RSS episodes into local metadata.")
    parser.add_argument("rss_url")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    imported, skipped = import_from_rss(args.rss_url, args.base_url)
    print(f"Imported {imported} episode(s), skipped {skipped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
