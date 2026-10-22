"""Small, edit-only web entry point for the private knowledge library."""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from services import db
from services import knowledge_document as document

BASE = ""
ORIGIN = os.getenv("KNOWLEDGE_WEB_ORIGIN", "").rstrip("/")
SYNC_TOKEN = os.getenv("KNOWLEDGE_SYNC_TOKEN", "")
templates = Jinja2Templates(directory="templates")


def _asset_version() -> str:
    digest = hashlib.sha256()
    assets = Path(__file__).resolve().parent / "knowledge_assets"
    for name in ("knowledge.css", "theme.js", "library.js", "article.js"):
        digest.update(name.encode("utf-8"))
        digest.update((assets / name).read_bytes())
    return digest.hexdigest()[:12]


ASSET_VERSION = _asset_version()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not Path(db.DB_PATH).is_file():
        raise RuntimeError(f"Knowledge database is missing: {db.DB_PATH}")
    with db.get_conn() as conn:
        conn.execute("SELECT 1 FROM articles LIMIT 1").fetchone()
    yield


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.mount(f"{BASE}/assets", StaticFiles(directory="knowledge_assets"), name="assets")
app.mount(f"{BASE}/static/images", StaticFiles(directory="static/images"), name="images")


@app.middleware("http")
async def protect_writes(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if ORIGIN and request.headers.get("origin") != ORIGIN and not _is_sync_request(request):
            return JSONResponse({"error": "invalid origin"}, status_code=403)
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            return JSONResponse({"error": "JSON required"}, status_code=415)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data: https:; media-src 'self' https:; "
        "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    )
    return response


def _is_sync_request(request: Request) -> bool:
    return bool(SYNC_TOKEN) and secrets.compare_digest(
        request.headers.get("x-knowledge-sync-key", ""), SYNC_TOKEN
    )


def _card(article: dict) -> dict:
    return {key: article.get(key) for key in (
        "id", "title", "summary", "source_type", "source_url", "image_url", "created_at", "tags", "word_count"
    )}


@app.get(f"{BASE}/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "knowledge_library.html", {"asset_version": ASSET_VERSION})


@app.get(f"{BASE}/article/{{article_id}}", response_class=HTMLResponse)
async def article_page(request: Request, article_id: str):
    if not db.get_article(article_id):
        return HTMLResponse("文章不存在", status_code=404)
    return templates.TemplateResponse(request, "knowledge_article.html", {"article_id": article_id, "asset_version": ASSET_VERSION})


@app.get(f"{BASE}/healthz")
async def healthz():
    return {"ok": True}


@app.get(f"{BASE}/api/articles")
async def articles(q: str = "", tag: str = "", offset: int = 0):
    offset = max(0, offset)
    selected_tag = tag.strip()[:40]
    rows = db.list_articles(query=q.strip()[:200] or None, tags=[selected_tag] if selected_tag else None, limit=41, offset=offset)
    return {"articles": [_card(a) for a in rows[:40]], "has_more": len(rows) > 40}


@app.get(f"{BASE}/api/tags")
async def tags():
    return {"tags": db.list_all_tags()}


@app.get(f"{BASE}/api/articles/{{article_id}}")
async def article(article_id: str):
    item = db.get_article(article_id)
    if not item:
        return JSONResponse({"error": "not found"}, status_code=404)
    return _card(item)


@app.get(f"{BASE}/api/articles/{{article_id}}/content")
async def content(article_id: str):
    if not db.get_article(article_id):
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        item = document.read_document(article_id)
    except (OSError, ValueError):
        return JSONResponse({"error": "article file unavailable"}, status_code=404)
    return {key: item[key] for key in ("content", "fallback", "revision")}


@app.get(f"{BASE}/api/articles/{{article_id}}/document")
async def get_document(article_id: str):
    try:
        item = document.read_document(article_id)
    except (OSError, ValueError):
        return JSONResponse({"error": "article file unavailable"}, status_code=404)
    return item if item else JSONResponse({"error": "not found"}, status_code=404)


def _document_error(error: Exception) -> JSONResponse:
    if isinstance(error, document.DocumentConflict):
        return JSONResponse({"error": str(error)}, status_code=409)
    if isinstance(error, KeyError):
        return JSONResponse({"error": "not found"}, status_code=404)
    if isinstance(error, ValueError):
        return JSONResponse({"error": str(error)}, status_code=400)
    return JSONResponse({"error": "save failed"}, status_code=500)


@app.put(f"{BASE}/api/articles/{{article_id}}/document")
async def put_document(article_id: str, request: Request):
    try:
        body = await request.json()
        return document.write_document(article_id, body, source="local" if _is_sync_request(request) else "web")
    except (ValueError, KeyError, document.DocumentConflict, OSError) as error:
        return _document_error(error)


@app.get(f"{BASE}/api/articles/{{article_id}}/history")
async def article_history(article_id: str):
    if not db.get_article(article_id):
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"history": document.history(article_id)}


@app.get(f"{BASE}/api/articles/{{article_id}}/history/{{revision_id}}")
async def article_history_version(article_id: str, revision_id: str):
    item = document.history_version(article_id, revision_id)
    return item if item else JSONResponse({"error": "not found"}, status_code=404)


@app.get(f"{BASE}/api/sync/manifest")
async def sync_manifest(request: Request):
    if not _is_sync_request(request):
        return JSONResponse({"error": "sync key required"}, status_code=403)
    with db.get_conn() as conn:
        ids = [row[0] for row in conn.execute("SELECT id FROM articles")]
    revisions = {}
    for article_id in ids:
        try:
            item = document.read_document(article_id)
        except (OSError, ValueError):
            continue
        revisions[article_id] = item["revision"]
    return {"revisions": revisions}


@app.post(f"{BASE}/api/sync/articles")
async def sync_create_article(request: Request):
    if not _is_sync_request(request):
        return JSONResponse({"error": "sync key required"}, status_code=403)
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("invalid document")
        images = body.pop("images", {})
        if not isinstance(images, dict) or len(images) > 30:
            raise ValueError("invalid images")
        image_dir = Path("static/images")
        image_dir.mkdir(parents=True, exist_ok=True)
        decoded = {}
        for name, encoded in images.items():
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}\.(?:png|jpe?g|gif|webp)", name, re.I):
                raise ValueError("invalid image name")
            if not isinstance(encoded, str):
                raise ValueError("invalid image data")
            try:
                decoded[name] = base64.b64decode(encoded, validate=True)
            except binascii.Error as error:
                raise ValueError("invalid image data") from error
        if sum(map(len, decoded.values())) > 12_000_000:
            raise ValueError("images too large")
        for name, data in decoded.items():
            path = image_dir / name
            if path.exists() and path.read_bytes() != data:
                raise document.DocumentConflict("image name collision")
        created = []
        try:
            for name, data in decoded.items():
                path = image_dir / name
                if not path.exists():
                    path.write_bytes(data)
                    created.append(path)
            result = document.create_document(body)
        except Exception:
            for path in created:
                path.unlink(missing_ok=True)
            raise
        return result
    except (ValueError, KeyError, document.DocumentConflict, OSError) as error:
        return _document_error(error)


@app.patch(f"{BASE}/api/articles/{{article_id}}")
async def update_article(article_id: str, request: Request):
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)
    if (not isinstance(body, dict) or not set(body) & {"title", "tags"}
            or set(body) - {"title", "tags", "revision"}
            or not isinstance(body.get("revision"), str)):
        return JSONResponse({"error": "title or tags required"}, status_code=400)
    try:
        current = document.read_document(article_id)
        if current is None:
            raise KeyError(article_id)
        current.update(body)
        result = document.write_document(article_id, current, source="web")
        return {"ok": True, "revision": result["revision"]}
    except (ValueError, KeyError, document.DocumentConflict, OSError) as error:
        return _document_error(error)


@app.put(f"{BASE}/api/articles/{{article_id}}/content")
async def update_content(article_id: str, request: Request):
    try:
        body = await request.json()
        if not isinstance(body, dict) or set(body) != {"content", "revision"}:
            raise ValueError("invalid content")
        current = document.read_document(article_id)
        if current is None:
            raise KeyError(article_id)
        current.update(body)
        result = document.write_document(article_id, current, source="web")
        return {"ok": True, "revision": result["revision"]}
    except (ValueError, KeyError, document.DocumentConflict, OSError) as error:
        return _document_error(error)
