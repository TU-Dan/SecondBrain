#!/usr/bin/env python3
"""Print a compact health report for the SecondBrain project."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "knowledge.db"
EPISODES_PATH = ROOT / "static" / "episodes.json"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    return result.returncode, (result.stdout or result.stderr).strip()


def print_section(title: str) -> None:
    print(f"\n## {title}")


def audit_git() -> None:
    print_section("Git")
    _, branch = run(["git", "branch", "--show-current"])
    code, status = run(["git", "status", "--short"])
    print(f"branch: {branch or 'unknown'}")
    if code == 0 and status:
        lines = status.splitlines()
        print(f"dirty files: {len(lines)}")
        for line in lines[:12]:
            print(f"  {line}")
        if len(lines) > 12:
            print(f"  ... {len(lines) - 12} more")
    elif code == 0:
        print("dirty files: 0")
    else:
        print(f"status error: {status}")


def audit_db() -> None:
    print_section("Database")
    if not DB_PATH.exists():
        print(f"missing: {DB_PATH}")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        tables = [
            "articles",
            "feeds",
            "feed_items",
            "inbox_items",
            "agent_tasks",
            "agent_proposals",
            "evolution_log",
        ]
        for table in tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"{table}: {count}")
            except sqlite3.Error as exc:
                print(f"{table}: error: {exc}")

        rows = conn.execute(
            "SELECT status, COUNT(*) AS count FROM agent_tasks GROUP BY status ORDER BY status"
        ).fetchall()
        if rows:
            summary = ", ".join(f"{row['status']}={row['count']}" for row in rows)
            print(f"agent task status: {summary}")
    finally:
        conn.close()


def local_episode_count() -> int | None:
    if not EPISODES_PATH.exists():
        return None
    try:
        with EPISODES_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return len(data) if isinstance(data, list) else None
    except Exception:
        return None


def remote_rss_count(base_url: str | None) -> int | None:
    if not base_url:
        return None
    url = f"{base_url.rstrip('/')}/podcast.xml"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "SecondBrainAudit/1.0"})
        with urllib.request.urlopen(request, timeout=10) as response:
            xml = response.read()
        root = ET.fromstring(xml)
        channel = root.find("channel")
        return len(channel.findall("item")) if channel is not None else 0
    except Exception as exc:
        print(f"remote RSS error: {exc}")
        return None


def audit_rss() -> None:
    print_section("RSS")
    local_count = local_episode_count()
    print(f"local episodes: {local_count if local_count is not None else 'unknown'}")
    base_url = os.getenv("GITHUB_PAGES_URL")
    if base_url:
        remote_count = remote_rss_count(base_url)
        print(f"remote episodes: {remote_count if remote_count is not None else 'unknown'}")
        print(f"remote RSS: {base_url.rstrip('/')}/podcast.xml")
    else:
        print("remote RSS: skipped, GITHUB_PAGES_URL is not set")


def audit_server(url: str) -> None:
    print_section("Server")
    try:
        with urllib.request.urlopen(url, timeout=4) as response:
            print(f"{url}: HTTP {response.status}")
    except Exception as exc:
        print(f"{url}: unavailable ({exc})")


def audit_files() -> None:
    print_section("Files")
    for path in ["main.py", "services/agent_loop.py", "services/db.py", "templates/article.html", "templates/library.html"]:
        full_path = ROOT / path
        if full_path.exists():
            with full_path.open("r", encoding="utf-8", errors="ignore") as f:
                line_count = sum(1 for _ in f)
            print(f"{path}: {line_count} lines")


def audit_cleanup_candidates() -> None:
    print_section("Cleanup Candidates")
    candidates = [
        (
            "Merge /generate into Inbox",
            "Keep route until file upload can create an inbox item and start podcast generation from there.",
        ),
        (
            "Merge /card into Article output panel",
            "Keep route until card preview/export works inside the article page.",
        ),
        (
            "Merge feed_items into inbox_items",
            "Requires a data migration because RSS status and relevance live in feed_items today.",
        ),
        (
            "Keep one-off maintenance scripts out of services/",
            "services/importer.py has been moved to scripts/import_remote_rss.py.",
        ),
    ]
    for title, note in candidates:
        print(f"- {title}: {note}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit local SecondBrain project health.")
    parser.add_argument("--server-url", default="http://127.0.0.1:8000/")
    parser.add_argument("--skip-server", action="store_true")
    return parser.parse_args()


def main() -> int:
    os.chdir(ROOT)
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except Exception:
        pass

    args = parse_args()
    print(f"# SecondBrain Audit: {ROOT}")
    audit_git()
    audit_db()
    audit_rss()
    audit_files()
    audit_cleanup_candidates()
    if not args.skip_server:
        audit_server(args.server_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
