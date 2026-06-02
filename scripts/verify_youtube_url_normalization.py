#!/usr/bin/env python3
"""Verify YouTube playlist URLs are normalized to one video before yt-dlp."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.extractor import normalize_video_url


def main() -> int:
    cases = {
        "https://www.youtube.com/watch?v=vXonLkOQ-iI&list=PLaZG-v9srSUefixvXgpwtwfLY-POQq9Lo&index=3":
            "https://www.youtube.com/watch?v=vXonLkOQ-iI",
        "https://www.youtube.com/watch?v=vXonLk0Q-iI&list=PLaZG-v9srSUefixvXgpwtwfLY-P0Qq9Lo&index=10":
            "https://www.youtube.com/watch?v=vXonLk0Q-iI",
        "https://youtu.be/vXonLkOQ-iI?si=abc":
            "https://www.youtube.com/watch?v=vXonLkOQ-iI",
        "https://www.youtube.com/shorts/vXonLkOQ-iI?feature=share":
            "https://www.youtube.com/watch?v=vXonLkOQ-iI",
        "https://www.youtube.com/embed/vXonLkOQ-iI?start=10":
            "https://www.youtube.com/watch?v=vXonLkOQ-iI",
    }
    for source, expected in cases.items():
        actual = normalize_video_url(source)
        assert actual == expected, (source, actual, expected)
    print("youtube url normalization ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
