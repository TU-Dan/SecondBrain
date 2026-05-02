from __future__ import annotations

"""
GBrain memory bridge.
Writes articles as markdown into brain/, syncs via gbrain CLI,
and queries the brain for recall and synthesis.
"""

import subprocess
import os
import re
import json
from datetime import datetime, timezone
from pathlib import Path

BRAIN_DIR = Path(__file__).parent.parent / "brain"
GBRAIN_BIN = Path.home() / ".bun" / "bin" / "gbrain"
ARTICLES_DIR = BRAIN_DIR / "articles"
INSIGHTS_DIR = BRAIN_DIR / "insights"
DAILY_DIR = BRAIN_DIR / "daily"


def _run(args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    env = {**os.environ, "PATH": f"{Path.home() / '.bun' / 'bin'}:{os.environ.get('PATH', '')}"}
    try:
        result = subprocess.run(
            [str(GBRAIN_BIN)] + args,
            capture_output=True, text=True, env=env,
            cwd=cwd or str(BRAIN_DIR),
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return 124, "", "gbrain command timed out"
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = slug.strip('-')[:80]
    return slug


def _article_to_markdown(article: dict) -> str:
    """Format an article dict as GBrain-compatible markdown."""
    title = article.get("title", "Untitled")
    source_url = article.get("source_url", "")
    source_type = article.get("source_type", "url")
    created_at = article.get("created_at", datetime.now(timezone.utc).isoformat())[:10]
    tags = article.get("tags") or []
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = []
    summary = article.get("summary", "")
    insights_raw = article.get("insights")
    insights = {}
    if insights_raw:
        try:
            insights = json.loads(insights_raw) if isinstance(insights_raw, str) else insights_raw
        except Exception:
            pass

    tags_yaml = ", ".join(f'"{t}"' for t in tags) if tags else ""
    source_line = f"[Source: {source_url}, {created_at}]" if source_url else f"[Source: {source_type}, {created_at}]"

    lines = [
        f"---",
        f"title: \"{title}\"",
        f"date: {created_at}",
        f"source: \"{source_url}\"",
        f"source_type: {source_type}",
    ]
    if tags_yaml:
        lines.append(f"tags: [{tags_yaml}]")
    lines += ["---", "", f"# {title}", "", f"{source_line}", ""]

    if summary:
        lines += [f"## 摘要", "", summary, ""]

    if insights:
        zh = insights.get("zh_translation", "")
        key_points = insights.get("key_points", [])
        if zh:
            lines += ["## 全文（中文）", "", zh[:3000], ""]
        if key_points:
            lines += ["## 核心观点", ""]
            for pt in key_points:
                lines.append(f"- {pt}")
            lines.append("")

    return "\n".join(lines)


def remember(article: dict) -> bool:
    """Write article to brain and sync to GBrain index."""
    article_id = article.get("id", "unknown")
    title = article.get("title", "Untitled")
    slug = _slugify(title) or f"article-{article_id[:8]}"

    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    md_path = ARTICLES_DIR / f"{slug}.md"
    md_path.write_text(_article_to_markdown(article), encoding="utf-8")

    code, out, err = _run(["import", str(ARTICLES_DIR), "--no-embed"])
    if code != 0:
        print(f"[memory] import warning: {err}")

    return code == 0


def embed_stale() -> bool:
    """Generate embeddings for newly synced content (requires OPENAI_API_KEY)."""
    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("VOYAGE_API_KEY")):
        return False
    code, out, err = _run(["embed", "--stale"])
    return code == 0


def recall(query: str, limit: int = 8) -> list[dict]:
    """Hybrid search: keyword + vector (vector requires OPENAI_API_KEY)."""
    code, out, err = _run(["query", query, "--json", f"--limit={limit}"])
    if code != 0 or not out:
        return _recall_keyword(query, limit)
    try:
        data = json.loads(out)
        if isinstance(data, list):
            return data
        return data.get("results", [])
    except Exception:
        return _recall_keyword(query, limit)


def _recall_keyword(query: str, limit: int = 8) -> list[dict]:
    """Fallback to keyword-only search."""
    code, out, err = _run(["search", query, "--json", f"--limit={limit}"])
    if code != 0 or not out:
        return []
    try:
        data = json.loads(out)
        if isinstance(data, list):
            return data
        return data.get("results", [])
    except Exception:
        return []


def synthesize(topic: str, limit: int = 15) -> str:
    """Ask GBrain to synthesize across memories on a topic."""
    code, out, err = _run(["query", topic, f"--limit={limit}"])
    return out if code == 0 else ""


def get_graph(slug: str, depth: int = 2) -> str:
    """Return typed relationship graph for an entity."""
    code, out, err = _run(["graph-query", slug, f"--depth={depth}"])
    return out if code == 0 else ""


def write_page(slug: str, title: str, body: str, subdir: str = "insights") -> bool:
    """Write an arbitrary markdown page to the brain."""
    target_dir = BRAIN_DIR / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    content = f"---\ntitle: \"{title}\"\ndate: {date}\n---\n\n# {title}\n\n{body}\n"
    (target_dir / f"{slug}.md").write_text(content, encoding="utf-8")
    code, _, err = _run(["import", str(target_dir), "--no-embed"])
    return code == 0


def stats() -> dict:
    """Return brain stats."""
    code, out, err = _run(["stats", "--json"])
    if code == 0 and out:
        try:
            return json.loads(out)
        except Exception:
            pass
    return {}
