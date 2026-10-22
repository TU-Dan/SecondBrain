"""Versioned article documents shared by the local app and the private web app."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from services import db

SCRIPTS_DIR = Path("static/scripts")
_write_lock = threading.RLock()


class DocumentConflict(Exception):
    pass


def _tags(value: object) -> list[str]:
    try:
        values = json.loads(value or "[]") if isinstance(value, str) else value
    except (ValueError, TypeError):
        values = []
    return values if isinstance(values, list) else []


def content_path(article: dict) -> Path | None:
    stored = article.get("article_md_path")
    if not stored:
        return None
    path = Path(str(stored).lstrip("/")).resolve()
    if not path.is_relative_to(SCRIPTS_DIR.resolve()) or path.suffix.lower() != ".md":
        raise ValueError("invalid article path")
    return path


def _content(article: dict) -> tuple[str, bool]:
    path = content_path(article)
    if path is None:
        return f"# {article.get('title') or '未命名文章'}\n\n{article.get('summary') or ''}".strip(), True
    return path.read_text(encoding="utf-8"), False


def revision(title: str, tags: list[str], content: str) -> str:
    payload = json.dumps([title, tags, content], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_document(article_id: str) -> dict | None:
    article = db.get_article(article_id)
    if article is None:
        return None
    content, fallback = _content(article)
    tags = _tags(article.get("tags"))
    return {
        "id": article_id,
        "title": article.get("title") or "",
        "tags": tags,
        "content": content,
        "fallback": fallback,
        "revision": revision(article.get("title") or "", tags, content),
        "summary": article.get("summary"),
        "source_url": article.get("source_url"),
        "source_type": article.get("source_type"),
        "image_url": article.get("image_url"),
        "created_at": article.get("created_at"),
        "word_count": article.get("word_count"),
    }


def validate_document(body: dict, *, require_revision: bool = True) -> tuple[str, list[str], str]:
    if not isinstance(body, dict):
        raise ValueError("invalid document")
    if require_revision and not isinstance(body.get("revision"), str):
        raise ValueError("revision required")
    title, tags, content = body.get("title"), body.get("tags"), body.get("content")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 300:
        raise ValueError("invalid title")
    if (not isinstance(tags, list) or len(tags) > 20
            or any(not isinstance(tag, str) or not 1 <= len(tag.strip()) <= 40 for tag in tags)):
        raise ValueError("invalid tags")
    if not isinstance(content, str) or len(content.encode("utf-8")) > 2_000_000:
        raise ValueError("invalid content")
    return title.strip(), list(dict.fromkeys(tag.strip() for tag in tags)), content


def _history_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS article_revisions (
            article_id TEXT NOT NULL,
            revision TEXT NOT NULL,
            title TEXT NOT NULL,
            tags TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (article_id, revision)
        )
    """)


def write_document(article_id: str, body: dict, *, source: str = "web") -> dict:
    title, tags, content = validate_document(body)
    with _write_lock:
        current = read_document(article_id)
        if current is None:
            raise KeyError(article_id)
        if body["revision"] != current["revision"]:
            raise DocumentConflict("文章已在其他位置修改，请重新加载后再保存")
        if (title, tags, content) == (current["title"], current["tags"], current["content"]):
            return current

        article = db.get_article(article_id)
        path = content_path(article)
        if path is None:
            safe_id = hashlib.sha256(article_id.encode("utf-8")).hexdigest()[:24]
            path = SCRIPTS_DIR.resolve() / f"manual_{safe_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = path.read_bytes() if path.exists() else None
        temp_name = None
        replaced = False
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp:
                temp_name = temp.name
                temp.write(content)
                temp.flush()
                os.fsync(temp.fileno())
            with db.get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                _history_table(conn)
                conn.execute("""
                    INSERT OR IGNORE INTO article_revisions
                    (article_id, revision, title, tags, content, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (article_id, current["revision"], current["title"],
                      json.dumps(current["tags"], ensure_ascii=False), current["content"],
                      source, datetime.now(timezone.utc).isoformat()))
                conn.execute("""
                    UPDATE articles SET title=?, tags=?, article_md_path=?, word_count=? WHERE id=?
                """, (title, json.dumps(tags, ensure_ascii=False),
                      article.get("article_md_path") or f"/static/scripts/{path.name}",
                      len(content), article_id))
                os.replace(temp_name, path)
                replaced = True
                conn.commit()
        except Exception:
            if replaced:
                if previous is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(previous)
            raise
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)
        return read_document(article_id)


def create_document(body: dict) -> dict:
    title, tags, content = validate_document(body, require_revision=False)
    article_id = body.get("id")
    if not isinstance(article_id, str) or not re.fullmatch(r"[0-9a-f]{32}", article_id):
        raise ValueError("invalid article id")
    if not isinstance(body.get("created_at"), str):
        raise ValueError("created_at required")
    with _write_lock:
        if db.get_article(article_id):
            raise DocumentConflict("article already exists")
        SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        path = SCRIPTS_DIR.resolve() / f"synced_{article_id}.md"
        if path.exists():
            raise DocumentConflict("article file already exists")
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp:
                temp_name = temp.name
                temp.write(content)
                temp.flush()
                os.fsync(temp.fileno())
            with db.get_conn() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("""
                    INSERT INTO articles
                    (id, title, source_url, source_type, tags, summary, article_md_path,
                     image_url, created_at, word_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (article_id, title, body.get("source_url"), body.get("source_type"),
                      json.dumps(tags, ensure_ascii=False), body.get("summary"),
                      f"/static/scripts/{path.name}", body.get("image_url"),
                      body["created_at"], len(content)))
                os.replace(temp_name, path)
                conn.commit()
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)
        return read_document(article_id)


def history(article_id: str) -> list[dict]:
    with db.get_conn() as conn:
        _history_table(conn)
        rows = conn.execute("""
            SELECT revision, title, tags, source, created_at FROM article_revisions
            WHERE article_id=? ORDER BY created_at DESC LIMIT 50
        """, (article_id,)).fetchall()
    return [dict(row) for row in rows]


def history_version(article_id: str, revision_id: str) -> dict | None:
    with db.get_conn() as conn:
        _history_table(conn)
        row = conn.execute("""
            SELECT revision, title, tags, content, source, created_at
            FROM article_revisions WHERE article_id=? AND revision=?
        """, (article_id, revision_id)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["tags"] = _tags(item["tags"])
    return item
