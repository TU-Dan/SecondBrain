"""Small, edit-only web entry point for the private knowledge library."""

from __future__ import annotations

import hashlib
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from services import db

BASE = ""
SCRIPTS_DIR = Path("static/scripts")
ORIGIN = os.getenv("KNOWLEDGE_WEB_ORIGIN", "").rstrip("/")
templates = Jinja2Templates(directory="templates")


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
        if ORIGIN and request.headers.get("origin") != ORIGIN:
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


def _revision(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _content_path(article: dict) -> Path | None:
    stored = article.get("article_md_path")
    if not stored:
        return None
    path = Path(str(stored).lstrip("/")).resolve()
    if not path.is_relative_to(SCRIPTS_DIR.resolve()) or path.suffix.lower() != ".md":
        raise ValueError("invalid article path")
    return path


def _read_content(article: dict) -> tuple[str, bool]:
    path = _content_path(article)
    if path is None:
        return f"# {article.get('title') or '未命名文章'}\n\n{article.get('summary') or ''}".strip(), True
    return path.read_text(encoding="utf-8"), False


def _card(article: dict) -> dict:
    return {key: article.get(key) for key in (
        "id", "title", "summary", "source_type", "source_url", "image_url", "created_at", "tags", "word_count"
    )}


@app.get(f"{BASE}/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "knowledge_library.html")


@app.get(f"{BASE}/article/{{article_id}}", response_class=HTMLResponse)
async def article_page(request: Request, article_id: str):
    if not db.get_article(article_id):
        return HTMLResponse("文章不存在", status_code=404)
    return templates.TemplateResponse(request, "knowledge_article.html", {"article_id": article_id})


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
    item = db.get_article(article_id)
    if not item:
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        body, fallback = _read_content(item)
    except (OSError, ValueError):
        return JSONResponse({"error": "article file unavailable"}, status_code=404)
    return {"content": body, "fallback": fallback, "revision": _revision(body)}


@app.patch(f"{BASE}/api/articles/{{article_id}}")
async def update_article(article_id: str, request: Request):
    if not db.get_article(article_id):
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)
    if not isinstance(body, dict) or not body or set(body) - {"title", "tags"}:
        return JSONResponse({"error": "title or tags required"}, status_code=400)
    if "title" in body and (not isinstance(body["title"], str) or not 1 <= len(body["title"].strip()) <= 300):
        return JSONResponse({"error": "invalid title"}, status_code=400)
    if "tags" in body and (
        not isinstance(body["tags"], list) or len(body["tags"]) > 20
        or any(not isinstance(tag, str) or not 1 <= len(tag.strip()) <= 40 for tag in body["tags"])
    ):
        return JSONResponse({"error": "invalid tags"}, status_code=400)
    if "title" in body:
        db.update_article_title(article_id, body["title"].strip())
    if "tags" in body:
        db.update_tags(article_id, list(dict.fromkeys(tag.strip() for tag in body["tags"])))
    return {"ok": True}


@app.put(f"{BASE}/api/articles/{{article_id}}/content")
async def update_content(article_id: str, request: Request):
    item = db.get_article(article_id)
    if not item:
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)
    if (not isinstance(body, dict) or not isinstance(body.get("content"), str)
            or len(body["content"].encode("utf-8")) > 2_000_000
            or not isinstance(body.get("revision"), str)):
        return JSONResponse({"error": "invalid content"}, status_code=400)
    try:
        current, _ = _read_content(item)
        path = _content_path(item)
    except (OSError, ValueError):
        return JSONResponse({"error": "article file unavailable"}, status_code=404)
    if body["revision"] != _revision(current):
        return JSONResponse({"error": "文章已被其他页面修改，请刷新后重试"}, status_code=409)
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    if path is None:
        safe_id = hashlib.sha256(article_id.encode("utf-8")).hexdigest()[:24]
        path = SCRIPTS_DIR.resolve() / f"manual_{safe_id}.md"
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp:
            temp_name = temp.name
            temp.write(body["content"])
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, path)
        if not item.get("article_md_path"):
            db.update_article_content_path(article_id, f"/static/scripts/{path.name}", len(body["content"]))
    except OSError:
        return JSONResponse({"error": "save failed"}, status_code=500)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return {"ok": True, "revision": _revision(body["content"])}
