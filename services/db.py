from __future__ import annotations

import sqlite3
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

DB_PATH = "data/knowledge.db"
SCRIPTS_DIR = "static/scripts"


def get_conn():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source_url TEXT,
                source_type TEXT,
                tags TEXT DEFAULT '[]',
                summary TEXT,
                article_md_path TEXT,
                transcript_path TEXT,
                audio_url TEXT,
                audio_length INTEGER,
                image_url TEXT,
                created_at TEXT,
                word_count INTEGER,
                insights TEXT
            )
        """)
        # Migration: add insights column if it doesn't exist
        try:
            conn.execute("ALTER TABLE articles ADD COLUMN insights TEXT")
        except Exception:
            pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feeds (
                id TEXT PRIMARY KEY,
                name TEXT,
                url TEXT NOT NULL,
                feed_type TEXT DEFAULT 'rss',
                last_fetched_at TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feed_items (
                id TEXT PRIMARY KEY,
                feed_id TEXT REFERENCES feeds(id) ON DELETE CASCADE,
                feed_name TEXT,
                title TEXT,
                url TEXT,
                description TEXT,
                published_at TEXT,
                relevance_score INTEGER DEFAULT 50,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inbox_items (
                id TEXT PRIMARY KEY,
                source TEXT DEFAULT 'manual',
                intent TEXT DEFAULT 'read',
                title TEXT NOT NULL,
                url TEXT,
                description TEXT,
                note TEXT,
                status TEXT DEFAULT 'pending',
                priority TEXT DEFAULT 'normal',
                created_at TEXT,
                updated_at TEXT,
                completed_at TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_inbox_items_status_intent_created
            ON inbox_items(status, intent, created_at)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS podcast_jobs (
                id TEXT PRIMARY KEY,
                source_url TEXT NOT NULL,
                source_type TEXT NOT NULL,
                options_json TEXT DEFAULT '{}',
                status TEXT DEFAULT 'pending',
                stage TEXT DEFAULT 'pending',
                message TEXT,
                files_json TEXT DEFAULT '[]',
                result_json TEXT DEFAULT '{}',
                error_code TEXT,
                error_message TEXT,
                created_at TEXT,
                updated_at TEXT,
                started_at TEXT,
                finished_at TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_podcast_jobs_status_created
            ON podcast_jobs(status, created_at)
        """)
        _ensure_columns(
            conn,
            "podcast_jobs",
            {
                "attempt_count": "INTEGER DEFAULT 1",
                "parent_job_id": "TEXT",
                "heartbeat_at": "TEXT",
                "cancel_requested_at": "TEXT",
                "timeout_at": "TEXT",
            },
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS podcast_job_events (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                stage TEXT,
                message TEXT,
                data_json TEXT DEFAULT '{}',
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_podcast_job_events_job_created
            ON podcast_job_events(job_id, created_at)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS highlights (
                id TEXT PRIMARY KEY,
                article_id TEXT NOT NULL,
                text TEXT NOT NULL,
                note TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS outputs (
                id TEXT PRIMARY KEY,
                article_id TEXT NOT NULL,
                format_type TEXT,
                pain_point TEXT,
                content TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_tasks (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                objective TEXT,
                success_criteria_json TEXT DEFAULT '[]',
                payload_json TEXT DEFAULT '{}',
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 50,
                review_required INTEGER DEFAULT 0,
                next_action TEXT,
                artifact_type TEXT,
                artifact_id TEXT,
                attempts INTEGER DEFAULT 0,
                scheduled_at TEXT,
                started_at TEXT,
                finished_at TEXT,
                result_json TEXT,
                error TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_tasks_status_schedule
            ON agent_tasks(status, scheduled_at, priority)
        """)
        _ensure_columns(
            conn,
            "agent_tasks",
            {
                "objective": "TEXT",
                "success_criteria_json": "TEXT DEFAULT '[]'",
                "review_required": "INTEGER DEFAULT 0",
                "next_action": "TEXT",
                "artifact_type": "TEXT",
                "artifact_id": "TEXT",
            },
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evolution_log (
                id TEXT PRIMARY KEY,
                task_id TEXT,
                event_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                before_json TEXT,
                after_json TEXT,
                artifact_type TEXT,
                artifact_id TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_evolution_log_created
            ON evolution_log(created_at)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_proposals (
                id TEXT PRIMARY KEY,
                task_id TEXT,
                kind TEXT DEFAULT 'js',
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                code TEXT NOT NULL,
                page_context_json TEXT DEFAULT '{}',
                risk_level TEXT DEFAULT 'medium',
                expected_effects_json TEXT DEFAULT '[]',
                status TEXT DEFAULT 'pending',
                result_json TEXT,
                error TEXT,
                created_at TEXT,
                approved_at TEXT,
                executed_at TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_proposals_status_created
            ON agent_proposals(status, created_at)
        """)
        conn.commit()
    _scan_scripts_dir()


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    """Add missing columns for lightweight SQLite migrations."""
    existing = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _parse_script(path: str) -> dict:
    """Extract title, created_at, summary, word_count from a script .md file."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()

    # Title: first # heading
    title = ""
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break

    # created_at: **生成时间**: line
    created_at = datetime.now(timezone.utc).isoformat()
    for line in lines:
        if "生成时间" in line:
            # format: **生成时间**: 2026-04-09 19:48
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', line)
            if match:
                try:
                    dt = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M")
                    created_at = dt.replace(tzinfo=timezone.utc).isoformat()
                except ValueError:
                    pass
            break

    # Body: everything after first ---
    body = ""
    sep_idx = content.find("\n---\n")
    if sep_idx != -1:
        body = content[sep_idx + 5:].strip()

    summary = body[:200].replace("\n", " ") if body else ""
    word_count = len(body)

    return {
        "title": title,
        "created_at": created_at,
        "summary": summary,
        "word_count": word_count,
    }


def _scan_scripts_dir():
    """Index all .md files in static/scripts/ that are not yet in the DB."""
    if not os.path.exists(SCRIPTS_DIR):
        return

    with get_conn() as conn:
        existing = {
            row[0] for row in conn.execute("SELECT article_md_path FROM articles WHERE article_md_path IS NOT NULL").fetchall()
        }

    added = 0
    for filename in sorted(os.listdir(SCRIPTS_DIR)):
        if not filename.endswith(".md"):
            continue
        url_path = f"/static/scripts/{filename}"
        if url_path in existing:
            continue

        file_path = os.path.join(SCRIPTS_DIR, filename)
        try:
            parsed = _parse_script(file_path)
        except Exception as e:
            print(f"[db] Failed to parse {filename}: {e}")
            continue
        if re.search(r"（第\d+段/共\d+段）", parsed["title"] or ""):
            continue

        add_article(
            title=parsed["title"] or filename,
            source_type="script",
            summary=parsed["summary"],
            article_md_path=url_path,
            word_count=parsed["word_count"],
            created_at_override=parsed["created_at"],
        )
        added += 1

    if added:
        print(f"[db] Indexed {added} scripts from {SCRIPTS_DIR}")


def add_article(
    title: str,
    source_url: str = None,
    source_type: str = None,
    summary: str = None,
    article_md_path: str = None,
    transcript_path: str = None,
    audio_url: str = None,
    audio_length: int = None,
    image_url: str = None,
    word_count: int = None,
    created_at_override: str = None,
) -> str:
    article_id = uuid.uuid4().hex
    created_at = created_at_override or datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO articles
                (id, title, source_url, source_type, summary, article_md_path,
                 transcript_path, audio_url, audio_length, image_url, created_at, word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            article_id, title, source_url, source_type, summary, article_md_path,
            transcript_path, audio_url, audio_length, image_url,
            created_at, word_count,
        ))
        conn.commit()
    return article_id


def list_articles(source_type: str = None, query: str = None, tags: list[str] = None, limit: int = 100, offset: int = 0) -> list[dict]:
    with get_conn() as conn:
        conditions = []
        params = []

        if query:
            conditions.append("(a.title LIKE ? OR a.summary LIKE ?)")
            pattern = f"%{query}%"
            params.extend([pattern, pattern])

        if source_type:
            conditions.append("a.source_type = ?")
            params.append(source_type)

        if tags:
            placeholders = ",".join("?" * len(tags))
            conditions.append(
                f"(SELECT COUNT(DISTINCT je.value) FROM json_each(a.tags) je WHERE je.value IN ({placeholders})) = ?"
            )
            params.extend(tags)
            params.append(len(tags))

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = conn.execute(
            f"SELECT a.* FROM articles a {where} ORDER BY a.created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def get_article(article_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
    return dict(row) if row else None


def get_untagged_articles() -> list[dict]:
    """Return articles that have no tags and have a script file."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM articles WHERE (tags IS NULL OR tags = '[]') AND article_md_path IS NOT NULL"
        ).fetchall()
    return [dict(r) for r in rows]


def update_insights(article_id: str, insights: dict):
    with get_conn() as conn:
        conn.execute(
            "UPDATE articles SET insights=? WHERE id=?",
            (json.dumps(insights, ensure_ascii=False), article_id)
        )
        conn.commit()


def update_tags(article_id: str, tags: list[str]):
    with get_conn() as conn:
        conn.execute(
            "UPDATE articles SET tags=? WHERE id=?",
            (json.dumps(tags, ensure_ascii=False), article_id)
        )
        conn.commit()


def list_all_tags() -> list[dict]:
    """Return all distinct tags with counts, sorted by frequency descending."""
    with get_conn() as conn:
        rows = conn.execute("SELECT tags FROM articles WHERE tags IS NOT NULL AND tags != '[]'").fetchall()
    freq: dict[str, int] = {}
    for row in rows:
        try:
            for tag in json.loads(row[0]):
                freq[tag] = freq.get(tag, 0) + 1
        except Exception:
            pass
    return [{"tag": t, "count": freq[t]} for t in sorted(freq, key=lambda t: -freq[t])]


def delete_article(article_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT article_md_path, transcript_path FROM articles WHERE id=?", (article_id,)).fetchone()
        cur = conn.execute("DELETE FROM articles WHERE id=?", (article_id,))
        conn.commit()
    if row:
        for path in (row[0], row[1]):
            if path:
                try:
                    os.remove(path.lstrip("/"))
                except FileNotFoundError:
                    pass
    return cur.rowcount > 0


def update_article_title(article_id: str, title: str):
    with get_conn() as conn:
        conn.execute("UPDATE articles SET title=? WHERE id=?", (title, article_id))
        conn.commit()


def update_article_summary(article_id: str, summary: str, word_count: int = None):
    with get_conn() as conn:
        if word_count is None:
            conn.execute("UPDATE articles SET summary=? WHERE id=?", (summary, article_id))
        else:
            conn.execute(
                "UPDATE articles SET summary=?, word_count=? WHERE id=?",
                (summary, word_count, article_id),
            )
        conn.commit()


def update_article_content_path(article_id: str, article_md_path: str, word_count: int = None):
    with get_conn() as conn:
        if word_count is None:
            conn.execute(
                "UPDATE articles SET article_md_path=? WHERE id=?",
                (article_md_path, article_id),
            )
        else:
            conn.execute(
                "UPDATE articles SET article_md_path=?, word_count=? WHERE id=?",
                (article_md_path, word_count, article_id),
            )
        conn.commit()


# ── Feed management ──────────────────────────────────────────────────────────

def add_feed(url: str, name: str, feed_type: str = "rss") -> str:
    feed_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO feeds (id, url, name, feed_type, created_at) VALUES (?,?,?,?,?)",
            (feed_id, url, name, feed_type, now),
        )
        conn.commit()
    return feed_id


def list_feeds() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM feeds ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def delete_feed(feed_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM feed_items WHERE feed_id=?", (feed_id,))
        conn.execute("DELETE FROM feeds WHERE id=?", (feed_id,))
        conn.commit()


def update_feed_fetched(feed_id: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE feeds SET last_fetched_at=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), feed_id),
        )
        conn.commit()


def upsert_feed_items(items: list[dict]):
    """Insert new feed items, skip duplicates by url."""
    with get_conn() as conn:
        existing = {r[0] for r in conn.execute("SELECT url FROM feed_items").fetchall()}
        for item in items:
            if item["url"] in existing:
                continue
            conn.execute(
                """INSERT INTO feed_items
                   (id, feed_id, feed_name, title, url, description, published_at, relevance_score, status, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    uuid.uuid4().hex,
                    item["feed_id"],
                    item.get("feed_name", ""),
                    item["title"],
                    item["url"],
                    item.get("description", ""),
                    item.get("published_at", ""),
                    item.get("relevance_score", 50),
                    "pending",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        conn.commit()


def list_inbox(min_score: int = 0) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM feed_items WHERE status='pending' AND relevance_score >= ?
               ORDER BY relevance_score DESC, created_at DESC LIMIT 100""",
            (min_score,),
        ).fetchall()
    return [dict(r) for r in rows]


def count_inbox() -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM feed_items WHERE status='pending'"
        ).fetchone()[0]


def update_feed_item_status(item_id: str, status: str):
    with get_conn() as conn:
        conn.execute("UPDATE feed_items SET status=? WHERE id=?", (status, item_id))
        conn.commit()


# ── Unified inbox / waiting list ─────────────────────────────────────────────

VALID_INBOX_INTENTS = {"podcast", "read", "todo", "note"}
VALID_INBOX_STATUSES = {"pending", "processing", "done", "archived", "dismissed", "saved"}
VALID_INBOX_PRIORITIES = {"low", "normal", "high"}


def _normalize_choice(value: str | None, allowed: set[str], default: str) -> str:
    value = (value or "").strip()
    return value if value in allowed else default


def add_inbox_item(
    title: str,
    url: str = None,
    intent: str = "read",
    description: str = None,
    note: str = None,
    priority: str = "normal",
    source: str = "manual",
) -> str:
    item_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    intent = _normalize_choice(intent, VALID_INBOX_INTENTS, "read")
    priority = _normalize_choice(priority, VALID_INBOX_PRIORITIES, "normal")
    title = (title or "").strip() or (url or "未命名")
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO inbox_items
               (id, source, intent, title, url, description, note, status, priority, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (item_id, source, intent, title, url, description, note, "pending", priority, now, now),
        )
        conn.commit()
    return item_id


def get_inbox_item(item_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM inbox_items WHERE id=?", (item_id,)).fetchone()
    return dict(row) if row else None


def update_inbox_item(item_id: str, **fields) -> bool:
    allowed = {"intent", "title", "url", "description", "note", "status", "priority"}
    updates = []
    params = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key == "intent":
            value = _normalize_choice(value, VALID_INBOX_INTENTS, "read")
        elif key == "status":
            value = _normalize_choice(value, VALID_INBOX_STATUSES, "pending")
        elif key == "priority":
            value = _normalize_choice(value, VALID_INBOX_PRIORITIES, "normal")
        updates.append(f"{key}=?")
        params.append(value)
    if not updates:
        return False
    updates.append("updated_at=?")
    params.append(datetime.now(timezone.utc).isoformat())
    if fields.get("status") == "done":
        updates.append("completed_at=?")
        params.append(datetime.now(timezone.utc).isoformat())
    params.append(item_id)
    with get_conn() as conn:
        cur = conn.execute(f"UPDATE inbox_items SET {', '.join(updates)} WHERE id=?", params)
        conn.commit()
    return cur.rowcount > 0


def delete_inbox_item(item_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM inbox_items WHERE id=?", (item_id,))
        conn.commit()
    return cur.rowcount > 0


# ── Podcast jobs ─────────────────────────────────────────────────────────────

def create_podcast_job(
    source_url: str,
    source_type: str,
    options: dict = None,
    *,
    parent_job_id: str | None = None,
    attempt_count: int = 1,
) -> str:
    job_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO podcast_jobs
               (id, source_url, source_type, options_json, status, stage, message,
                files_json, result_json, attempt_count, parent_job_id, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                job_id,
                source_url,
                source_type,
                json.dumps(options or {}, ensure_ascii=False),
                "pending",
                "pending",
                "任务已提交，等待处理...",
                "[]",
                "{}",
                attempt_count,
                parent_job_id,
                now,
                now,
            ),
        )
        conn.commit()
    add_podcast_job_event(job_id, "created", "pending", "任务已提交，等待处理。")
    return job_id


def get_podcast_job(job_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM podcast_jobs WHERE id=?", (job_id,)).fetchone()
    return _decode_podcast_job(row)


def list_podcast_jobs(status: str | None = None, limit: int = 100) -> list[dict]:
    query = "SELECT * FROM podcast_jobs"
    params: list = []
    if status and status != "all":
        query += " WHERE status=?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        pending_ids = [
            row["id"]
            for row in conn.execute(
                "SELECT id FROM podcast_jobs WHERE status='pending' ORDER BY created_at ASC"
            ).fetchall()
        ]
    positions = {job_id: index + 1 for index, job_id in enumerate(pending_ids)}
    jobs = []
    for row in rows:
        job = _decode_podcast_job(row)
        job["queue_position"] = positions.get(job["id"])
        jobs.append(job)
    return jobs


def get_podcast_job_events(job_id: str, limit: int = 200) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM podcast_job_events
               WHERE job_id=? ORDER BY created_at ASC LIMIT ?""",
            (job_id, limit),
        ).fetchall()
    events = []
    for row in rows:
        event = dict(row)
        try:
            event["data"] = json.loads(event.get("data_json") or "{}")
        except Exception:
            event["data"] = {}
        events.append(event)
    return events


def add_podcast_job_event(
    job_id: str,
    event_type: str,
    stage: str | None,
    message: str,
    data: dict | None = None,
) -> str:
    event_id = uuid.uuid4().hex
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO podcast_job_events
               (id, job_id, event_type, stage, message, data_json, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                event_id,
                job_id,
                event_type,
                stage,
                message,
                json.dumps(data or {}, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    return event_id


def get_next_podcast_job() -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM podcast_jobs
               WHERE status='pending'
               ORDER BY created_at ASC
               LIMIT 1"""
        ).fetchone()
    return _decode_podcast_job(row)


def claim_podcast_job(job_id: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """UPDATE podcast_jobs
               SET status='running', stage='resolving', started_at=?, updated_at=?,
                   heartbeat_at=?, cancel_requested_at=NULL, timeout_at=NULL,
                   error_code=NULL, error_message=NULL
               WHERE id=? AND status='pending'""",
            (now, now, now, job_id),
        )
        conn.commit()
    claimed = cur.rowcount > 0
    if claimed:
        add_podcast_job_event(job_id, "started", "resolving", "任务开始执行。")
    return claimed


def update_podcast_job(job_id: str, **fields) -> None:
    allowed = {
        "status", "stage", "message", "files_json", "result_json",
        "error_code", "error_message", "started_at", "finished_at",
        "attempt_count", "parent_job_id", "heartbeat_at",
        "cancel_requested_at", "timeout_at",
    }
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    columns = ", ".join(f"{key}=?" for key in updates)
    values = list(updates.values()) + [job_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE podcast_jobs SET {columns} WHERE id=?", values)
        conn.commit()


def append_podcast_job_file(job_id: str, file: dict) -> None:
    job = get_podcast_job(job_id)
    if not job:
        return
    files = job.get("files") or []
    files.append(file)
    update_podcast_job(job_id, files_json=json.dumps(files, ensure_ascii=False))
    add_podcast_job_event(job_id, "file", job.get("stage"), file.get("label", "生成文件"), file)


def request_podcast_job_cancel(job_id: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        job = conn.execute(
            "SELECT status, options_json FROM podcast_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if not job or job["status"] not in {"pending", "running"}:
            return False
        cur = conn.execute(
            """UPDATE podcast_jobs
               SET status=CASE WHEN status='pending' THEN 'cancelled' ELSE 'cancelling' END,
                   stage=CASE WHEN status='pending' THEN 'cancelled' ELSE stage END,
                   message=CASE WHEN status='pending' THEN '任务已取消。' ELSE '正在取消任务...' END,
                   cancel_requested_at=?, finished_at=CASE WHEN status='pending' THEN ? ELSE finished_at END,
                   updated_at=?
               WHERE id=? AND status IN ('pending','running')""",
            (now, now, now, job_id),
        )
        conn.commit()
    if cur.rowcount:
        if job["status"] == "pending":
            add_podcast_job_event(job_id, "cancelled", "cancelled", "任务已取消。")
            try:
                inbox_item_id = json.loads(job["options_json"] or "{}").get("inbox_item_id")
            except Exception:
                inbox_item_id = None
            if inbox_item_id:
                update_inbox_item(inbox_item_id, status="pending")
        else:
            add_podcast_job_event(job_id, "cancel_requested", None, "已请求取消任务。")
    return cur.rowcount > 0


def retry_podcast_job(job_id: str) -> str | None:
    job = get_podcast_job(job_id)
    if not job or job["status"] not in {"failed", "cancelled"}:
        return None
    return create_podcast_job(
        job["source_url"],
        job["source_type"],
        job.get("options") or {},
        parent_job_id=job_id,
        attempt_count=int(job.get("attempt_count") or 1) + 1,
    )


def delete_podcast_job(job_id: str) -> bool:
    with get_conn() as conn:
        job = conn.execute("SELECT status FROM podcast_jobs WHERE id=?", (job_id,)).fetchone()
        if not job or job["status"] in {"running", "cancelling"}:
            return False
        conn.execute("DELETE FROM podcast_job_events WHERE job_id=?", (job_id,))
        cur = conn.execute("DELETE FROM podcast_jobs WHERE id=?", (job_id,))
        conn.commit()
    return cur.rowcount > 0


def cleanup_podcast_jobs(days: int = 30) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, days))).isoformat()
    with get_conn() as conn:
        ids = [
            row["id"]
            for row in conn.execute(
                """SELECT id FROM podcast_jobs
                   WHERE status IN ('done','failed','cancelled') AND updated_at < ?""",
                (cutoff,),
            ).fetchall()
        ]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        conn.execute(f"DELETE FROM podcast_job_events WHERE job_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM podcast_jobs WHERE id IN ({placeholders})", ids)
        conn.commit()
    return len(ids)


def reset_running_podcast_jobs() -> int:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        running = conn.execute(
            """UPDATE podcast_jobs
               SET status='pending', stage='pending',
                   message='服务已重启，任务已重新放回队列。',
                   started_at=NULL, heartbeat_at=NULL, cancel_requested_at=NULL, updated_at=?
               WHERE status='running'""",
            (now,),
        )
        cancelling_jobs = [
            dict(row)
            for row in conn.execute(
                "SELECT id, options_json FROM podcast_jobs WHERE status='cancelling'"
            ).fetchall()
        ]
        conn.execute(
            """UPDATE podcast_jobs
               SET status='cancelled', stage='cancelled', message='任务已取消。',
                   error_code='cancelled', error_message='任务由用户取消。',
                   finished_at=?, heartbeat_at=NULL, updated_at=?
               WHERE status='cancelling'""",
            (now, now),
        )
        conn.commit()
    for job in cancelling_jobs:
        job_id = job["id"]
        add_podcast_job_event(job_id, "cancelled", "cancelled", "服务重启后完成取消。")
        try:
            inbox_item_id = json.loads(job["options_json"] or "{}").get("inbox_item_id")
        except Exception:
            inbox_item_id = None
        if inbox_item_id:
            update_inbox_item(inbox_item_id, status="pending")
    return running.rowcount


def _decode_podcast_job(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    job = dict(row)
    for raw_key, decoded_key, fallback in (
        ("options_json", "options", {}),
        ("files_json", "files", []),
        ("result_json", "result", {}),
    ):
        try:
            job[decoded_key] = json.loads(job.get(raw_key) or json.dumps(fallback))
        except Exception:
            job[decoded_key] = fallback
    return job


def list_manual_inbox_items(intent: str = None, status: str = "pending", limit: int = 100) -> list[dict]:
    conditions = []
    params = []
    if status:
        conditions.append("status=?")
        params.append(status)
    if intent and intent != "all":
        conditions.append("intent=?")
        params.append(intent)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM inbox_items {where} ORDER BY created_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def list_unified_inbox(intent: str = None, status: str = "pending", min_score: int = 0, limit: int = 150) -> list[dict]:
    manual = []
    if intent in (None, "", "all", "podcast", "read", "todo", "note"):
        manual_intent = None if intent in (None, "", "all") else intent
        manual = list_manual_inbox_items(intent=manual_intent, status=status, limit=limit)

    unified = []
    for item in manual:
        unified.append({
            **item,
            "kind": "manual",
            "feed_name": "",
            "relevance_score": None,
            "published_at": "",
        })

    if intent in (None, "", "all", "rss", "read") and status == "pending":
        for item in list_inbox(min_score=min_score):
            unified.append({
                **item,
                "kind": "rss",
                "intent": "read",
                "source": "rss",
                "note": "",
                "priority": "normal",
            })

    priority_rank = {"high": 0, "normal": 1, "low": 2}
    unified.sort(key=lambda item: (
        priority_rank.get(item.get("priority"), 1),
        -(item.get("relevance_score") or 0),
        item.get("created_at") or "",
    ))
    unified.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    unified.sort(key=lambda item: priority_rank.get(item.get("priority"), 1))
    return unified[:limit]


def count_unified_inbox() -> int:
    with get_conn() as conn:
        manual_count = conn.execute(
            "SELECT COUNT(*) FROM inbox_items WHERE status='pending'"
        ).fetchone()[0]
    return manual_count + count_inbox()


# ── Article counts ────────────────────────────────────────────────────────────

def count_by_type() -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT source_type, COUNT(*) as n FROM articles GROUP BY source_type"
        ).fetchall()
    return {r["source_type"]: r["n"] for r in rows}


# ── Highlights ────────────────────────────────────────────────────────────────

def add_highlight(article_id: str, text: str) -> str:
    hid = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO highlights (id, article_id, text, created_at) VALUES (?,?,?,?)",
            (hid, article_id, text, now),
        )
        conn.commit()
    return hid


def list_highlights(article_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM highlights WHERE article_id=? ORDER BY created_at ASC",
            (article_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_highlight(highlight_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM highlights WHERE id=?", (highlight_id,)).fetchone()
    return dict(row) if row else None


def update_highlight_note(highlight_id: str, note: str):
    with get_conn() as conn:
        conn.execute("UPDATE highlights SET note=? WHERE id=?", (note, highlight_id))
        conn.commit()


def delete_highlight(highlight_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM highlights WHERE id=?", (highlight_id,))
        conn.commit()


# ── Outputs ───────────────────────────────────────────────────────────────────

def save_output(article_id: str, format_type: str, content: str, pain_point: str = "") -> str:
    oid = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO outputs (id, article_id, format_type, pain_point, content, created_at) VALUES (?,?,?,?,?,?)",
            (oid, article_id, format_type, pain_point, content, now),
        )
        conn.commit()
    return oid


def list_outputs(article_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM outputs WHERE article_id=? ORDER BY created_at DESC LIMIT 50",
            (article_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_output(output_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM outputs WHERE id=?", (output_id,))
        conn.commit()


# ── Agent tasks & evolution log ──────────────────────────────────────────────

def enqueue_agent_task(
    task_type: str,
    title: str,
    payload: dict = None,
    priority: int = 50,
    scheduled_at: str = None,
    objective: str = None,
    success_criteria: list[str] = None,
    review_required: bool = False,
    next_action: str = None,
    artifact_type: str = None,
    artifact_id: str = None,
) -> str:
    task_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    scheduled = scheduled_at or now
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO agent_tasks
               (id, type, title, objective, success_criteria_json,
                payload_json, status, priority, review_required, next_action,
                artifact_type, artifact_id, attempts,
                scheduled_at, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                task_id,
                task_type,
                title,
                objective,
                json.dumps(success_criteria or [], ensure_ascii=False),
                json.dumps(payload or {}, ensure_ascii=False),
                "pending",
                priority,
                1 if review_required else 0,
                next_action,
                artifact_type,
                artifact_id,
                0,
                scheduled,
                now,
                now,
            ),
        )
        conn.commit()
    return task_id


def list_agent_tasks(status: str = None, limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM agent_tasks WHERE status=? ORDER BY priority DESC, scheduled_at ASC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agent_tasks ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [_decode_agent_task(r) for r in rows]


def get_next_agent_task():
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM agent_tasks
               WHERE status='pending' AND scheduled_at <= ?
               ORDER BY priority DESC, scheduled_at ASC, created_at ASC
               LIMIT 1""",
            (now,),
        ).fetchone()
    return _decode_agent_task(row) if row else None


def reset_stale_agent_tasks(timeout_minutes: int = 45) -> int:
    """Return stuck running tasks to pending so the queue can recover."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """UPDATE agent_tasks
               SET status='pending',
                   error='任务运行超时，已自动放回队列。',
                   updated_at=?
               WHERE status='running'
                 AND started_at IS NOT NULL
                 AND started_at <= ?""",
            (datetime.now(timezone.utc).isoformat(), cutoff),
        )
        conn.commit()
    return cur.rowcount


def get_agent_task(task_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM agent_tasks WHERE id=?", (task_id,)).fetchone()
    return _decode_agent_task(row) if row else None


def update_agent_task(task_id: str, **fields):
    allowed = {
        "status", "attempts", "started_at", "finished_at",
        "result_json", "error", "scheduled_at", "updated_at",
        "objective", "success_criteria_json", "review_required", "next_action",
        "artifact_type", "artifact_id",
    }
    if "success_criteria" in fields:
        fields["success_criteria_json"] = json.dumps(fields.pop("success_criteria") or [], ensure_ascii=False)
    if "review_required" in fields:
        fields["review_required"] = 1 if fields["review_required"] else 0
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    columns = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [task_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE agent_tasks SET {columns} WHERE id=?", values)
        conn.commit()


def _decode_agent_task(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    task = dict(row)
    raw_criteria = task.get("success_criteria_json") or "[]"
    try:
        task["success_criteria"] = json.loads(raw_criteria)
    except Exception:
        task["success_criteria"] = []
    task["review_required"] = bool(task.get("review_required"))
    return task


def add_evolution_log(
    event_type: str,
    summary: str,
    task_id: str = None,
    before: dict = None,
    after: dict = None,
    artifact_type: str = None,
    artifact_id: str = None,
) -> str:
    log_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO evolution_log
               (id, task_id, event_type, summary, before_json, after_json,
                artifact_type, artifact_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                log_id,
                task_id,
                event_type,
                summary,
                json.dumps(before, ensure_ascii=False) if before is not None else None,
                json.dumps(after, ensure_ascii=False) if after is not None else None,
                artifact_type,
                artifact_id,
                now,
            ),
        )
        conn.commit()
    return log_id


def list_evolution_log(limit: int = 80) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT l.*, t.type AS task_type, t.title AS task_title, t.status AS task_status
               FROM evolution_log l
               LEFT JOIN agent_tasks t ON t.id = l.task_id
               ORDER BY l.created_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Agent proposals ─────────────────────────────────────────────────────────

def create_agent_proposal(
    *,
    title: str,
    summary: str,
    code: str,
    kind: str = "js",
    page_context: dict = None,
    risk_level: str = "medium",
    expected_effects: list[str] = None,
    task_id: str = None,
) -> dict:
    proposal_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO agent_proposals
               (id, task_id, kind, title, summary, code, page_context_json,
                risk_level, expected_effects_json, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                proposal_id,
                task_id,
                kind,
                title,
                summary,
                code,
                json.dumps(page_context or {}, ensure_ascii=False),
                risk_level,
                json.dumps(expected_effects or [], ensure_ascii=False),
                "pending",
                now,
                now,
            ),
        )
        conn.commit()
    return get_agent_proposal(proposal_id)


def _decode_proposal(row: sqlite3.Row | None) -> dict | None:
    if not row:
        return None
    item = dict(row)
    for key, fallback in (("page_context_json", {}), ("expected_effects_json", []), ("result_json", None)):
        value = item.get(key)
        out_key = key.removesuffix("_json")
        if value is None:
            item[out_key] = fallback
            continue
        try:
            item[out_key] = json.loads(value)
        except Exception:
            item[out_key] = fallback
    return item


def get_agent_proposal(proposal_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM agent_proposals WHERE id=?", (proposal_id,)).fetchone()
    return _decode_proposal(row)


def list_agent_proposals(status: str = None, limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM agent_proposals WHERE status=? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agent_proposals ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [_decode_proposal(r) for r in rows]


def update_agent_proposal(proposal_id: str, **fields) -> dict | None:
    allowed = {
        "status", "result_json", "error", "approved_at",
        "executed_at", "updated_at",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_agent_proposal(proposal_id)
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    columns = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [proposal_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE agent_proposals SET {columns} WHERE id=?", values)
        conn.commit()
    return get_agent_proposal(proposal_id)
