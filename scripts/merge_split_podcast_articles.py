#!/usr/bin/env python3
"""Merge split podcast article rows into one readable article.

Podcast audio may stay split into multiple RSS episodes, but the knowledge
library should keep one article per source. This script repairs older rows that
were created as one article per audio part.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "knowledge.db"
SCRIPTS_DIR = ROOT / "static" / "scripts"
EPISODE_SCRIPTS_DIR = SCRIPTS_DIR / "episodes"
PART_RE = re.compile(r"^(?P<title>.+?)\s*（第(?P<part>\d+)段/共(?P<total>\d+)段）$")


def sanitize_filename(title: str) -> str:
    safe = re.sub(r"[^\w\u4e00-\u9fff]", "_", title)
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe[:50] or "untitled"


def script_body(path: str | None) -> str:
    if not path:
        return ""
    file_path = ROOT / path.lstrip("/")
    if not file_path.exists():
        return ""
    content = file_path.read_text(encoding="utf-8")
    sep_idx = content.find("\n---\n")
    return content[sep_idx + 5:].strip() if sep_idx != -1 else content.strip()


def write_combined_script(title: str, sections: list[tuple[int, str]]) -> str:
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{sanitize_filename(title)}_{ts}.md"
    path = SCRIPTS_DIR / filename
    body = "\n\n".join(f"## 第 {idx} 段\n\n{text}" for idx, text in sections if text.strip())
    content = f"""# {title}

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

{body}
"""
    path.write_text(content, encoding="utf-8")
    return f"/static/scripts/{filename}"


def move_part_script(path: str | None) -> str | None:
    if not path:
        return None
    src = ROOT / path.lstrip("/")
    if not src.exists() or src.parent != SCRIPTS_DIR:
        return path
    EPISODE_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    dst = EPISODE_SCRIPTS_DIR / src.name
    if dst.exists():
        src.unlink()
    else:
        shutil.move(str(src), str(dst))
    return f"/static/scripts/episodes/{dst.name}"


def merge_groups(title_filter: str | None = None, dry_run: bool = False) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT *
            FROM articles
            WHERE title LIKE '%（第%段/共%段）'
            ORDER BY created_at ASC
        """).fetchall()

        groups: dict[tuple[str, int], list[sqlite3.Row]] = {}
        for row in rows:
            match = PART_RE.match(row["title"] or "")
            if not match:
                continue
            base_title = match.group("title").strip()
            if title_filter and title_filter not in base_title:
                continue
            key = (base_title, int(match.group("total")))
            groups.setdefault(key, []).append(row)

        merged = 0
        for (base_title, total), group_rows in groups.items():
            parts = []
            for row in group_rows:
                match = PART_RE.match(row["title"] or "")
                if match:
                    parts.append((int(match.group("part")), row))
            parts.sort(key=lambda item: item[0])
            if len(parts) < 2:
                continue

            existing_parts = {idx for idx, _ in parts}
            missing = [idx for idx in range(1, total + 1) if idx not in existing_parts]
            if missing:
                print(f"skip incomplete: {base_title} missing parts {missing}")
                continue

            print(f"merge: {base_title} ({len(parts)} parts)")
            if dry_run:
                merged += 1
                continue

            sections = [(idx, script_body(row["article_md_path"])) for idx, row in parts]
            combined_path = write_combined_script(base_title, sections)
            combined_body = script_body(combined_path)
            summary = combined_body[:200].replace("\n", " ")
            word_count = len(combined_body)
            keep = parts[0][1]
            delete_ids = [row["id"] for _, row in parts[1:]]

            for _, row in parts:
                move_part_script(row["article_md_path"])

            conn.execute("""
                UPDATE articles
                SET title=?,
                    summary=?,
                    article_md_path=?,
                    word_count=?,
                    created_at=?,
                    source_url=?,
                    source_type=?,
                    transcript_path=?,
                    audio_url=?,
                    audio_length=?,
                    image_url=?
                WHERE id=?
            """, (
                base_title,
                summary,
                combined_path,
                word_count,
                keep["created_at"],
                keep["source_url"],
                keep["source_type"],
                keep["transcript_path"],
                keep["audio_url"],
                keep["audio_length"],
                keep["image_url"],
                keep["id"],
            ))
            conn.executemany("DELETE FROM articles WHERE id=?", [(article_id,) for article_id in delete_ids])
            conn.commit()
            merged += 1
        return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge split podcast article cards into one article.")
    parser.add_argument("--title", help="Only merge groups whose base title contains this text.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    merged = merge_groups(title_filter=args.title, dry_run=args.dry_run)
    print(f"merged groups: {merged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
