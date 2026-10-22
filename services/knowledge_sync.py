"""Synchronize local articles with the private web library over HTTPS."""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from services import db
from services import knowledge_document as document

IMAGE_REF = re.compile(r"/static/images/([A-Za-z0-9_-]{1,100}\.(?:png|jpe?g|gif|webp))", re.I)


class SyncError(Exception):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


def enabled() -> bool:
    return all(os.getenv(name) for name in (
        "KNOWLEDGE_SYNC_URL", "KNOWLEDGE_SYNC_USER",
        "KNOWLEDGE_SYNC_PASSWORD", "KNOWLEDGE_SYNC_TOKEN"
    ))


def _request(path: str, *, method: str = "GET", body: dict | None = None) -> dict:
    if not enabled():
        raise SyncError("知识库同步尚未配置")
    base = os.environ["KNOWLEDGE_SYNC_URL"].rstrip("/")
    if not base.startswith("https://"):
        raise SyncError("同步地址必须使用 HTTPS")
    credentials = f"{os.environ['KNOWLEDGE_SYNC_USER']}:{os.environ['KNOWLEDGE_SYNC_PASSWORD']}"
    auth = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        base + path, data=payload, method=method,
        headers={
            "Authorization": f"Basic {auth}",
            "X-Knowledge-Sync-Key": os.environ["KNOWLEDGE_SYNC_TOKEN"],
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:
            message = json.load(error).get("error", f"HTTP {error.code}")
        except (ValueError, OSError):
            message = f"HTTP {error.code}"
        raise SyncError(message, error.code) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise SyncError("无法连接网页知识库") from error


def fetch_document(article_id: str) -> dict | None:
    try:
        return _request(f"/api/articles/{article_id}/document")
    except SyncError as error:
        if error.status == 404:
            return None
        raise


def save_document(article_id: str, body: dict) -> dict:
    return _request(f"/api/articles/{article_id}/document", method="PUT", body=body)


def _images_for(article: dict) -> dict[str, str]:
    refs = set(IMAGE_REF.findall(article["content"]))
    refs.update(IMAGE_REF.findall(article.get("image_url") or ""))
    images = {}
    total = 0
    for name in refs:
        path = Path("static/images") / name
        if not path.is_file():
            raise SyncError(f"文章图片缺失：{name}")
        data = path.read_bytes()
        total += len(data)
        if total > 12_000_000:
            raise SyncError("文章图片总大小超过 12 MB")
        images[name] = base64.b64encode(data).decode("ascii")
    return images


def publish_article(article_id: str) -> dict:
    item = document.read_document(article_id)
    if item is None:
        raise SyncError("本地文章不存在")
    body = {key: item[key] for key in (
        "id", "title", "tags", "content", "summary", "source_url",
        "source_type", "image_url", "created_at"
    )}
    body["images"] = _images_for(item)
    return _request("/api/sync/articles", method="POST", body=body)


def _state(article_id: str) -> tuple[str, str] | None:
    with db.get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_sync_state (
                article_id TEXT PRIMARY KEY, remote_revision TEXT NOT NULL,
                local_revision TEXT NOT NULL, synced_at TEXT NOT NULL
            )
        """)
        row = conn.execute("""
            SELECT remote_revision, local_revision FROM knowledge_sync_state WHERE article_id=?
        """, (article_id,)).fetchone()
    return tuple(row) if row else None


def _record(article_id: str, remote_revision: str, local_revision: str) -> None:
    with db.get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_sync_state (
                article_id TEXT PRIMARY KEY, remote_revision TEXT NOT NULL,
                local_revision TEXT NOT NULL, synced_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            INSERT INTO knowledge_sync_state VALUES (?, ?, ?, ?)
            ON CONFLICT(article_id) DO UPDATE SET
                remote_revision=excluded.remote_revision,
                local_revision=excluded.local_revision,
                synced_at=excluded.synced_at
        """, (article_id, remote_revision, local_revision, datetime.now(timezone.utc).isoformat()))


def _backup_local(item: dict) -> None:
    folder = Path("data/knowledge_sync_conflicts")
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    path = folder / f"{item['id']}_{stamp}.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(item, stream, ensure_ascii=False, indent=2)


def apply_remote(item: dict, *, backup_if_different: bool = False) -> dict:
    local = document.read_document(item["id"])
    if local is None:
        raise SyncError("本地缺少对应文章，无法更新副本")
    if local["revision"] != item["revision"]:
        if backup_if_different:
            _backup_local(local)
        document.write_document(item["id"], {
            "title": item["title"], "tags": item["tags"],
            "content": item["content"], "revision": local["revision"],
        }, source="server")
    local = document.read_document(item["id"])
    _record(item["id"], item["revision"], local["revision"])
    return local


def read_canonical(article_id: str) -> dict | None:
    """Read the server and refresh a local mirror only when it has no local edits."""
    remote = fetch_document(article_id)
    if remote is None:
        return None
    local = document.read_document(article_id)
    if local is None:
        return remote
    state = _state(article_id)
    if local["revision"] == remote["revision"]:
        if state != (remote["revision"], local["revision"]):
            _record(article_id, remote["revision"], local["revision"])
    elif state and local["revision"] == state[1]:
        apply_remote(remote)
    else:
        remote["local_conflict"] = True
    return remote


def synchronize(*, apply: bool = False, accept_server_for_initial_conflicts: bool = False) -> dict:
    """Dry-run by default; never guess which side wins a conflicting edit."""
    manifest = _request("/api/sync/manifest")["revisions"]
    result = {"new": [], "pull": [], "push": [], "conflicts": [], "same": [], "errors": []}
    with db.get_conn() as conn:
        ids = [row[0] for row in conn.execute("SELECT id FROM articles ORDER BY created_at")]
    for article_id in ids:
        try:
            local = document.read_document(article_id)
            remote_revision = manifest.get(article_id)
            state = _state(article_id)
            if remote_revision is None:
                action = "new"
                if apply:
                    remote = publish_article(article_id)
                    _record(article_id, remote["revision"], local["revision"])
            elif state is None:
                action = "same" if local["revision"] == remote_revision else "conflicts"
                if apply and action == "same":
                    _record(article_id, remote_revision, local["revision"])
                elif apply and action == "conflicts" and accept_server_for_initial_conflicts:
                    remote = fetch_document(article_id)
                    apply_remote(remote, backup_if_different=True)
                    action = "pull"
            elif local["revision"] == state[1] and remote_revision == state[0]:
                action = "same"
            elif local["revision"] == state[1]:
                action = "pull"
                if apply:
                    remote = fetch_document(article_id)
                    apply_remote(remote)
            elif remote_revision == state[0]:
                action = "push"
                if apply:
                    remote = save_document(article_id, {
                        "title": local["title"], "tags": local["tags"],
                        "content": local["content"], "revision": remote_revision,
                    })
                    _record(article_id, remote["revision"], local["revision"])
            elif local["revision"] == remote_revision:
                action = "same"
                if apply:
                    _record(article_id, remote_revision, local["revision"])
            else:
                action = "conflicts"
            result[action].append(article_id)
        except (SyncError, OSError, ValueError, document.DocumentConflict) as error:
            result["errors"].append({"id": article_id, "error": str(error)})
    return result
