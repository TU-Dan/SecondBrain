import asyncio
import json
import logging
import threading
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
from fastapi import FastAPI, Request, Form, File, UploadFile, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "packages", "content-to-podcast"))

from curl_cffi import requests as cffi_requests
from services.extractor import detect_url_platform, download_youtube_audio, extract_content
from services.llm import distill_and_translate, format_transcript, chunk_text, polish_chunk, detect_language, generate_tags, generate_title, generate_social_post, extract_insights, generate_daily_brief, CHUNK_THRESHOLD
from services.tts import generate_audio_sync
from services import db
from services.db import (
    init_db, add_article, update_tags, get_untagged_articles,
    delete_article, update_article_title, update_insights,
    add_feed, list_feeds, delete_feed,
    list_inbox, count_inbox, update_feed_item_status, get_article,
    add_inbox_item, count_unified_inbox, delete_inbox_item, get_inbox_item,
    list_unified_inbox, update_inbox_item,
)
from services.feeds import refresh_all_feeds, refresh_feed, resolve_feed_url


def _remember_in_bg(article_id: str):
    """Background: index article into GBrain, queue ReAct analysis via task queue."""
    from services.db import get_article
    from services import memory
    from services.agent_tasks import enqueue_article_evolution
    article = get_article(article_id)
    if article:
        memory.remember(article)
        enqueue_article_evolution(article_id)
        # connect_article task now runs agent_loop ReAct — no direct on_article_added call


def _retag_untagged():
    """Background thread: generate tags for articles that have none."""
    articles = get_untagged_articles()
    if not articles:
        return
    print(f"[retag] Found {len(articles)} untagged articles, generating tags...")
    for a in articles:
        path = a["article_md_path"].lstrip("/")
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            continue
        tags = generate_tags(a["title"], content[:2000])
        if tags:
            update_tags(a["id"], tags)
            print(f"[retag] {a['title'][:30]} → {tags}")
    print("[retag] Done.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    init_db()
    threading.Thread(target=_retag_untagged, daemon=True).start()
    from services import agent
    from services import podcast_jobs
    agent.start()
    podcast_jobs.start()
    yield
    podcast_jobs.stop()
    agent.stop()


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def sanitize_filename(title: str) -> str:
    safe = re.sub(r'[^\w\u4e00-\u9fff]', '_', title)
    safe = re.sub(r'_+', '_', safe).strip('_')
    return safe[:50]


def download_thumbnail(thumbnail_url: str) -> str | None:
    """Download remote thumbnail to static/images/. Returns local URL path."""
    import urllib.request
    os.makedirs("static/images", exist_ok=True)
    try:
        req = urllib.request.Request(
            thumbnail_url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            content_type = resp.headers.get_content_type() or "image/jpeg"
            ext = "png" if "png" in content_type else "jpg"
            filename = f"{uuid.uuid4().hex}.{ext}"
            path = os.path.join("static/images", filename)
            with open(path, "wb") as f:
                f.write(resp.read())
        return f"/static/images/{filename}"
    except Exception as e:
        print(f"Failed to download thumbnail: {e}")
        return None


def save_transcript(title: str, text: str, source_type: str) -> str:
    """Save raw transcript as Markdown. Returns relative URL path."""
    os.makedirs("static/transcripts", exist_ok=True)
    lang = detect_language(text)
    lang_label = "中文" if lang == "zh" else "英文"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{sanitize_filename(title)}_逐字稿_{ts}.md"
    path = os.path.join("static/transcripts", filename)

    note = "" if lang == "zh" else "\n\n> 英文原稿，中文播客文稿见对应的文稿文件。"

    content = f"""# {title} — 原始逐字稿

**来源类型**: {source_type}
**处理时间**: {datetime.now().strftime("%Y-%m-%d %H:%M")}
**原文语言**: {lang_label}
{note}

---

{text}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"/static/transcripts/{filename}"


def save_script(title: str, script: str, part_label: str = "") -> str:
    """Save podcast script as Markdown. Returns relative URL path."""
    os.makedirs("static/scripts", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    part_suffix = f"_{part_label}" if part_label else ""
    filename = f"{sanitize_filename(title)}{part_suffix}_{ts}.md"
    path = os.path.join("static/scripts", filename)

    display_title = f"{title} {part_label}".strip()
    content = f"""# {display_title}

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

{script}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"/static/scripts/{filename}"


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def library(request: Request):
    return templates.TemplateResponse(request=request, name="library.html")


@app.get("/card", response_class=HTMLResponse)
async def card_page(request: Request):
    return templates.TemplateResponse(request=request, name="card.html")


@app.get("/generate", response_class=HTMLResponse)
async def generate_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/brief")
async def api_brief():
    import random
    from services.db import list_articles
    all_articles = list_articles(limit=200)
    if not all_articles:
        return JSONResponse({"error": "知识库暂无文章"}, status_code=404)

    # Prefer articles with summaries; mix recent + random older
    with_summary = [a for a in all_articles if a.get("summary")]
    pool = with_summary if with_summary else all_articles

    recent = pool[:10]
    older = pool[10:]
    picks = random.sample(recent, min(3, len(recent)))
    if older:
        picks += random.sample(older, min(2, len(older)))
    random.shuffle(picks)

    brief = generate_daily_brief(picks)
    if not brief:
        return JSONResponse({"error": "生成失败"}, status_code=500)

    return JSONResponse({
        "brief": brief,
        "articles": [{"id": a["id"], "title": a["title"]} for a in picks],
    })


@app.get("/api/tags")
async def api_tags():
    from services.db import list_all_tags
    return JSONResponse(list_all_tags())


@app.get("/api/articles")
async def api_articles(source_type: str = None, q: str = None, tags: str = None, limit: int = 100, offset: int = 0):
    from services.db import list_articles, count_by_type
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    articles = list_articles(source_type=source_type, query=q, tags=tag_list, limit=limit, offset=offset)
    counts = count_by_type()
    return JSONResponse({"articles": articles, "counts": counts})


@app.get("/article/{article_id}", response_class=HTMLResponse)
async def article_page(request: Request, article_id: str):
    from services.db import get_article
    article = get_article(article_id)
    if not article:
        return HTMLResponse("Not found", status_code=404)
    return templates.TemplateResponse(request=request, name="article.html", context={"article": article})


@app.get("/api/articles/{article_id}")
async def api_article(article_id: str):
    from services.db import get_article
    article = get_article(article_id)
    if not article:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(article)


@app.get("/api/articles/{article_id}/content")
async def get_article_content(article_id: str):
    from services.db import get_article
    article = get_article(article_id)
    if not article:
        return JSONResponse({"error": "not found"}, status_code=404)
    if not article.get("article_md_path"):
        fallback = article.get("summary") or ""
        if not fallback:
            fallback = "正文还没有写入。可能是后台入库任务仍在提取内容，或原链接无法抓取正文。"
        content = f"# {article.get('title') or '未命名文章'}\n\n{fallback}"
        return JSONResponse({"content": content, "fallback": True})
    # article_md_path is like /static/scripts/foo.md — strip leading /
    file_path = article["article_md_path"].lstrip("/")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return JSONResponse({"content": content})
    except FileNotFoundError:
        return JSONResponse({"error": "file not found"}, status_code=404)


@app.delete("/api/articles/{article_id}")
async def delete_article_route(article_id: str):
    ok = delete_article(article_id)
    return JSONResponse({"ok": ok}, status_code=200 if ok else 404)


@app.patch("/api/articles/{article_id}")
async def patch_article(article_id: str, request: Request):
    from services.db import get_article
    if not get_article(article_id):
        return JSONResponse({"error": "not found"}, status_code=404)
    body = await request.json()
    if "title" in body:
        update_article_title(article_id, body["title"])
    return JSONResponse({"ok": True})


@app.put("/api/articles/{article_id}/tags")
async def save_article_tags(article_id: str, request: Request):
    from services.db import get_article, update_tags
    if not get_article(article_id):
        return JSONResponse({"error": "not found"}, status_code=404)
    body = await request.json()
    tags = body.get("tags", [])
    update_tags(article_id, tags)
    return JSONResponse({"ok": True})


@app.post("/api/articles/{article_id}/insights")
async def generate_insights(article_id: str):
    from services.db import get_article
    article = get_article(article_id)
    if not article or not article.get("article_md_path"):
        return JSONResponse({"error": "not found"}, status_code=404)
    file_path = article["article_md_path"].lstrip("/")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return JSONResponse({"error": "file not found"}, status_code=404)
    insights = extract_insights(content)
    if not insights:
        return JSONResponse({"error": "提取失败，请检查 API Key"}, status_code=500)
    update_insights(article_id, insights)
    return JSONResponse({"ok": True, "insights": insights})


@app.post("/api/articles/{article_id}/post")
async def generate_post(article_id: str, request: Request):
    from services.db import get_article
    article = get_article(article_id)
    if not article or not article.get("article_md_path"):
        return JSONResponse({"error": "not found"}, status_code=404)

    body = await request.json()
    format_type = body.get("format", "wechat")
    pain_point = body.get("pain_point", "")

    file_path = article["article_md_path"].lstrip("/")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return JSONResponse({"error": "file not found"}, status_code=404)

    result = generate_social_post(content, format_type=format_type, pain_point=pain_point)
    if result is None:
        return JSONResponse({"error": "生成失败，请检查 API Key"}, status_code=500)
    from services.db import save_output
    save_output(article_id, format_type, result, pain_point)
    return JSONResponse({"ok": True, "content": result})


@app.get("/api/brain/query")
async def api_brain_query(q: str, limit: int = 8):
    """Hybrid search across GBrain memory."""
    from services import memory
    results = await asyncio.to_thread(memory.recall, q, limit)
    return JSONResponse({"query": q, "results": results})


@app.get("/api/brain/synthesize")
async def api_brain_synthesize(topic: str):
    """Cross-article synthesis on a topic."""
    from services import memory
    text = await asyncio.to_thread(memory.synthesize, topic)
    return JSONResponse({"topic": topic, "synthesis": text})


@app.get("/api/brain/graph")
async def api_brain_graph(slug: str, depth: int = 2):
    """Entity relationship graph traversal."""
    from services import memory
    graph = await asyncio.to_thread(memory.get_graph, slug, depth)
    return JSONResponse({"slug": slug, "graph": graph})


@app.get("/api/brain/stats")
async def api_brain_stats():
    """GBrain memory statistics."""
    from services import memory
    return JSONResponse(memory.stats())


@app.get("/api/agent/tasks")
async def api_agent_tasks(status: str = None, limit: int = 50):
    from services import db
    return JSONResponse(db.list_agent_tasks(status=status, limit=limit))


@app.post("/api/agent/tasks")
async def api_create_agent_task(request: Request):
    from services import db
    body = await request.json()
    task_type = (body.get("type") or "manual_agent_task").strip()
    title = (body.get("title") or body.get("objective") or "Agent 任务").strip()
    task_id = db.enqueue_agent_task(
        task_type,
        title,
        body.get("payload") or {},
        priority=int(body.get("priority") or 50),
        scheduled_at=body.get("scheduled_at"),
        objective=body.get("objective"),
        success_criteria=body.get("success_criteria") or [],
        review_required=bool(body.get("review_required")),
        next_action=body.get("next_action") or "等待 Agent 调度执行。",
        artifact_type=body.get("artifact_type"),
        artifact_id=body.get("artifact_id"),
    )
    task = db.get_agent_task(task_id)
    db.add_evolution_log(
        "task_created",
        f"创建 Agent 任务：{title}",
        task_id=task_id,
        after={
            "objective": body.get("objective"),
            "success_criteria": body.get("success_criteria") or [],
        },
        artifact_type=body.get("artifact_type"),
        artifact_id=body.get("artifact_id"),
    )
    return JSONResponse(task, status_code=201)


@app.post("/api/agent/tasks/{task_id}/run")
async def api_run_agent_task(task_id: str):
    from services import agent_tasks
    result = await asyncio.to_thread(agent_tasks.run_task_now, task_id)
    return JSONResponse(result, status_code=200 if result.get("ok") else 400)


@app.get("/api/agent/evolution")
async def api_evolution_log(limit: int = 80):
    from services import db
    return JSONResponse(db.list_evolution_log(limit=limit))


@app.get("/api/agent/proposals")
async def api_agent_proposals(status: str = None, limit: int = 50):
    from services import db
    return JSONResponse(db.list_agent_proposals(status=status, limit=limit))


@app.post("/api/agent/proposals/{proposal_id}/approve")
async def api_approve_agent_proposal(proposal_id: str):
    from services import agent_proposals
    result = agent_proposals.approve(proposal_id)
    return JSONResponse(result, status_code=200 if result.get("ok") else 400)


@app.post("/api/agent/proposals/{proposal_id}/reject")
async def api_reject_agent_proposal(proposal_id: str):
    from services import agent_proposals
    result = agent_proposals.reject(proposal_id)
    return JSONResponse(result, status_code=200 if result.get("ok") else 400)


@app.post("/api/agent/proposals/{proposal_id}/result")
async def api_agent_proposal_result(proposal_id: str, request: Request):
    from services import agent_proposals
    body = await request.json()
    result = agent_proposals.record_result(
        proposal_id,
        ok=bool(body.get("ok")),
        result=body.get("result") or {},
        error=body.get("error"),
    )
    return JSONResponse(result, status_code=200 if result.get("ok") else 400)


@app.get("/api/insights")
async def api_list_insights():
    """List all insight markdown files from brain/insights/."""
    import glob
    import re as _re
    insights_dir = os.path.join("brain", "insights")
    if not os.path.isdir(insights_dir):
        return JSONResponse([])
    results = []
    for path in sorted(glob.glob(os.path.join(insights_dir, "*.md")), reverse=True):
        slug = os.path.splitext(os.path.basename(path))[0]
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception:
            continue
        title = slug
        date = ""
        body = raw
        if raw.startswith("---"):
            end = raw.find("---", 3)
            if end != -1:
                fm = raw[3:end]
                body = raw[end + 3:].strip()
                m = _re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', fm, _re.MULTILINE)
                if m:
                    title = m.group(1).strip()
                m = _re.search(r'^date:\s*(.+?)\s*$', fm, _re.MULTILINE)
                if m:
                    date = m.group(1).strip()
        # First non-empty non-heading line as preview
        preview = ""
        for line in body.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                preview = line[:160]
                break
        results.append({"slug": slug, "title": title, "date": str(date), "preview": preview})
    return JSONResponse(results)


@app.get("/api/insights/{slug}")
async def api_get_insight(slug: str):
    """Return full markdown body of a single insight."""
    import re as _re
    path = os.path.join("brain", "insights", f"{slug}.md")
    if not os.path.isfile(path):
        return JSONResponse({"error": "not found"}, status_code=404)
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    title = slug
    date = ""
    body = raw
    if raw.startswith("---"):
        end = raw.find("---", 3)
        if end != -1:
            fm = raw[3:end]
            body = raw[end + 3:].strip()
            m = _re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', fm, _re.MULTILINE)
            if m:
                title = m.group(1).strip()
            m = _re.search(r'^date:\s*(.+?)\s*$', fm, _re.MULTILINE)
            if m:
                date = m.group(1).strip()
    return JSONResponse({"slug": slug, "title": title, "date": str(date), "body": body})


@app.post("/api/chat")
async def api_chat(request: Request):
    """Agent chat — streams NDJSON events (one JSON object per line)."""
    from services.agent_loop import run_stream
    import queue as _queue

    body = await request.json()
    message = body.get("message", "").strip()
    history = body.get("history", [])
    page_context = body.get("page_context") or {}

    if not message:
        return JSONResponse({"error": "message required"}, status_code=400)

    action_keywords = (
        "改", "修改", "更新", "删除", "新增", "添加", "保存", "跳转",
        "打开", "重命名", "生成标签", "重新生成", "刷新页面", "页面上",
    )
    if page_context and any(k in message for k in action_keywords):
        message = (
            "这条用户消息可能是页面/数据操作指令。"
            "如果需要修改当前页面或调用页面 API，请使用 propose_js 创建 JS 提案，等待用户确认后执行。\n\n"
            f"用户原始消息：{message}"
        )

    async def generate():
        loop = asyncio.get_event_loop()
        q: _queue.Queue = _queue.Queue()

        def _run():
            try:
                for event in run_stream(message, history=history, page_context=page_context):
                    q.put(event)
            finally:
                q.put(None)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        while True:
            event = await loop.run_in_executor(None, q.get)
            if event is None:
                break
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson; charset=utf-8")


@app.get("/api/articles/{article_id}/outputs")
async def api_list_outputs(article_id: str):
    from services.db import list_outputs
    return JSONResponse(list_outputs(article_id))


@app.delete("/api/outputs/{output_id}")
async def api_delete_output(output_id: str):
    from services.db import delete_output
    delete_output(output_id)
    return JSONResponse({"ok": True})


@app.post("/api/articles/{article_id}/pain-points")
async def api_suggest_pain_points(article_id: str):
    from services.db import get_article
    from services.llm import suggest_pain_points
    article = get_article(article_id)
    if not article or not article.get("article_md_path"):
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    try:
        with open(article["article_md_path"].lstrip("/"), "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return JSONResponse({"ok": False, "error": "file not found"}, status_code=404)
    points = suggest_pain_points(content)
    return JSONResponse({"ok": True, "points": points})


@app.post("/api/articles/{article_id}/batch-slice")
async def api_batch_slice(article_id: str, request: Request):
    from services.db import get_article, save_output
    from services.llm import generate_social_post
    article = get_article(article_id)
    if not article or not article.get("article_md_path"):
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    body = await request.json()
    pain_points = body.get("pain_points", [])[:5]
    format_type = body.get("format", "wechat")
    if not pain_points:
        return JSONResponse({"ok": False, "error": "no pain points"}, status_code=400)
    try:
        with open(article["article_md_path"].lstrip("/"), "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return JSONResponse({"ok": False, "error": "file not found"}, status_code=404)
    results = []
    for pp in pain_points:
        text = generate_social_post(content, format_type=format_type, pain_point=pp)
        if text:
            save_output(article_id, format_type, text, pp)
            results.append({"pain_point": pp, "content": text})
    return JSONResponse({"ok": True, "results": results})


@app.post("/api/articles/{article_id}/batch-cards")
async def api_batch_cards(article_id: str):
    from services.db import get_article, save_output
    from services.llm import batch_generate_cards
    article = get_article(article_id)
    if not article or not article.get("article_md_path"):
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    try:
        with open(article["article_md_path"].lstrip("/"), "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return JSONResponse({"ok": False, "error": "file not found"}, status_code=404)
    cards = batch_generate_cards(content, count=4)
    for card in cards:
        save_output(article_id, "card", card, "")
    return JSONResponse({"ok": True, "cards": cards})


@app.post("/api/articles/{article_id}/content")
async def save_article_content(article_id: str, request: Request):
    from services.db import get_article
    article = get_article(article_id)
    if not article or not article.get("article_md_path"):
        return JSONResponse({"error": "not found"}, status_code=404)
    file_path = article["article_md_path"].lstrip("/")
    body = await request.json()
    content = body.get("content", "")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/highlights")
async def api_all_highlights():
    """Return all highlights across all articles, joined with article title."""
    from services.db import get_conn
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT h.*, a.title as article_title
            FROM highlights h
            LEFT JOIN articles a ON h.article_id = a.id
            ORDER BY h.created_at DESC
        """).fetchall()
    return JSONResponse([dict(r) for r in rows])


@app.post("/api/articles/{article_id}/highlights")
async def api_add_highlight(article_id: str, request: Request):
    body = await request.json()
    text = body.get("text", "").strip()
    if not text:
        return JSONResponse({"ok": False, "error": "empty"}, status_code=400)
    from services.db import add_highlight
    hid = add_highlight(article_id, text)
    # Trigger agent analysis in background — highlight = strongest user signal
    if len(text) >= 20:
        from services.agent_tasks import enqueue_highlight_analysis
        threading.Thread(
            target=enqueue_highlight_analysis,
            args=(article_id, text),
            daemon=True,
        ).start()
    return JSONResponse({"ok": True, "id": hid})


@app.get("/api/articles/{article_id}/highlights")
async def api_list_highlights(article_id: str):
    from services.db import list_highlights
    return JSONResponse(list_highlights(article_id))


@app.post("/api/highlights/{highlight_id}/refine")
async def api_refine_highlight(highlight_id: str):
    from services.db import get_highlight, update_highlight_note
    from services.llm import refine_atomic_note
    h = get_highlight(highlight_id)
    if not h:
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    note = refine_atomic_note(h["text"])
    if note:
        update_highlight_note(highlight_id, note)
    return JSONResponse({"ok": bool(note), "note": note})


@app.delete("/api/highlights/{highlight_id}")
async def api_delete_highlight(highlight_id: str):
    from services.db import delete_highlight
    delete_highlight(highlight_id)
    return JSONResponse({"ok": True})


@app.post("/api/articles/{article_id}/related")
async def api_related_articles(article_id: str):
    import json as _json
    from services.db import list_highlights, list_articles, get_article
    from services.llm import find_related_articles
    article = get_article(article_id)
    if not article:
        return JSONResponse({"ok": False}, status_code=404)
    highlights = list_highlights(article_id)
    highlight_texts = [h.get("note") or h["text"] for h in highlights]
    if not highlight_texts:
        return JSONResponse({"ok": True, "related": []})
    all_arts = list_articles(limit=200)
    candidates = [a for a in all_arts if a["id"] != article_id]
    current_tags = set(_json.loads(article.get("tags") or "[]"))
    if current_tags:
        scored = sorted(candidates, key=lambda c: -len(current_tags & set(_json.loads(c.get("tags") or "[]"))))
        candidates = scored[:20]
    else:
        candidates = candidates[:20]
    related = find_related_articles(article["title"], highlight_texts, candidates)
    return JSONResponse({"ok": True, "related": related})


@app.post("/api/save/text")
async def quick_save_text(request: Request):
    """Save pasted text directly into the knowledge base (no LLM)."""
    body = await request.json()
    text = body.get("text", "").strip()
    if not text:
        return JSONResponse({"error": "text required"}, status_code=400)
    title = body.get("title", "").strip() or generate_title(text)
    script_url = save_script(title, text)
    summary = text[:200].replace("\n", " ")
    article_id = add_article(
        title=title,
        source_type="txt",
        summary=summary,
        article_md_path=script_url,
        word_count=len(text),
    )
    threading.Thread(target=_remember_in_bg, args=(article_id,), daemon=True).start()
    return JSONResponse({"ok": True, "article_id": article_id, "title": title})


@app.post("/api/save/url")
async def quick_save_url(request: Request):
    """Save a URL immediately without LLM processing."""
    body = await request.json()
    url = body.get("url", "").strip()
    if not url:
        return JSONResponse({"error": "url required"}, status_code=400)

    source_type = detect_url_platform(url)
    text, thumbnail_url = extract_content(url, source_type)
    if not text:
        return JSONResponse({"error": "无法提取内容，请检查链接"}, status_code=422)

    title = generate_title(text)
    episode_image = download_thumbnail(thumbnail_url) if thumbnail_url else None
    summary = text[:200].replace("\n", " ")
    script_url = save_script(title, text)

    article_id = add_article(
        title=title,
        source_url=url,
        source_type=source_type,
        summary=summary,
        article_md_path=script_url,
        image_url=episode_image,
        word_count=len(text),
    )
    threading.Thread(target=_remember_in_bg, args=(article_id,), daemon=True).start()
    return JSONResponse({"ok": True, "article_id": article_id, "title": title})


# ── Feed / Inbox endpoints ────────────────────────────────────────────────────

@app.get("/api/feeds")
async def api_list_feeds():
    return JSONResponse(list_feeds())


@app.post("/api/feeds")
async def api_add_feed(request: Request):
    body = await request.json()
    url = body.get("url", "").strip()
    name = body.get("name", "").strip()
    if not url:
        return JSONResponse({"ok": False, "error": "url required"}, status_code=400)
    rss_url, feed_type = await resolve_feed_url(url)
    if not name:
        name = url.split("/")[-1] or url
    feed_id = add_feed(rss_url, name, feed_type)
    feeds = list_feeds()
    feed = next(f for f in feeds if f["id"] == feed_id)
    # Kick off background fetch for this new feed
    import asyncio
    asyncio.create_task(refresh_feed(feed))
    return JSONResponse({"ok": True, "id": feed_id, "url": rss_url, "feed_type": feed_type})


@app.delete("/api/feeds/{feed_id}")
async def api_delete_feed(feed_id: str):
    delete_feed(feed_id)
    return JSONResponse({"ok": True})


@app.post("/api/feeds/refresh")
async def api_refresh_feeds():
    n = await refresh_all_feeds()
    return JSONResponse({"ok": True, "new_items": n})


@app.post("/api/discovery/run")
async def api_run_discovery():
    """Manually trigger a discovery run."""
    from services.discovery import run_daily_discovery
    result = await run_daily_discovery()
    return JSONResponse(result)


@app.get("/api/discovery/debug")
async def api_discovery_debug():
    """Run a full discovery cycle and return step-by-step trace."""
    from services.discovery import run_discovery_sync
    result = await asyncio.to_thread(run_discovery_sync)
    return JSONResponse(result)


@app.get("/api/inbox")
async def api_inbox(min_score: int = 0, intent: str = None):
    items = list_unified_inbox(intent=intent, min_score=min_score)
    return JSONResponse({"items": items, "count": len(items)})


@app.get("/api/inbox/count")
async def api_inbox_count():
    return JSONResponse({"count": count_unified_inbox()})


@app.post("/api/inbox/items")
async def api_create_inbox_item(request: Request):
    body = await request.json()
    url = (body.get("url") or "").strip()
    title = (body.get("title") or "").strip()
    note = (body.get("note") or "").strip()
    description = (body.get("description") or "").strip()
    intent = (body.get("intent") or ("read" if url else "todo")).strip()
    priority = (body.get("priority") or "normal").strip()

    if not title and not url and not note:
        return JSONResponse({"ok": False, "error": "title, url, or note required"}, status_code=400)

    if not title:
        title = url or note[:60] or "未命名"

    item_id = add_inbox_item(
        title=title,
        url=url or None,
        intent=intent,
        description=description or None,
        note=note or None,
        priority=priority,
        source=body.get("source") or "manual",
    )
    return JSONResponse({"ok": True, "id": item_id})


@app.patch("/api/inbox/items/{item_id}")
async def api_patch_inbox_item(item_id: str, request: Request):
    body = await request.json()
    allowed = {"intent", "title", "url", "description", "note", "status", "priority"}
    fields = {k: body[k] for k in allowed if k in body}
    ok = update_inbox_item(item_id, **fields)
    return JSONResponse({"ok": ok}, status_code=200 if ok else 404)


@app.delete("/api/inbox/items/{item_id}")
async def api_delete_inbox_item(item_id: str):
    ok = delete_inbox_item(item_id)
    return JSONResponse({"ok": ok}, status_code=200 if ok else 404)


@app.post("/api/inbox/items/{item_id}/podcast")
async def api_inbox_item_to_podcast(item_id: str, request: Request, background_tasks: BackgroundTasks):
    item = get_inbox_item(item_id)
    if not item:
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    url = (item.get("url") or "").strip()
    if not url:
        return JSONResponse({"ok": False, "error": "这条收件箱内容没有 URL，无法生成播客"}, status_code=400)

    from services import podcast_jobs
    source_type = detect_url_platform(url)
    base_url = str(request.base_url).rstrip('/')
    title = item.get("title") or ""
    job_id = podcast_jobs.enqueue(url, source_type, {
        "title": title,
        "base_url": base_url,
        "voice": "zh-CN-YunxiNeural",
        "use_original_audio": True,
        "summarize": False,
    })
    update_inbox_item(item_id, status="processing")
    return JSONResponse({"ok": True, "job_id": job_id})


@app.post("/api/inbox/{item_id}/save")
async def api_inbox_save(item_id: str, background_tasks: BackgroundTasks):
    from services.db import get_conn
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM feed_items WHERE id=?", (item_id,)).fetchone()
    if not row:
        return JSONResponse({"ok": False, "error": "not found"}, status_code=404)
    item = dict(row)
    update_feed_item_status(item_id, "saved")

    from services.extractor import extract_from_url
    from services.llm import detect_language, translate_full_article, generate_tags as gen_tags

    def _save():
        text, image_url_extracted = extract_from_url(item["url"])
        title = item["title"]
        tags = []
        if not text:
            script_url = None
            summary = item.get("description", "")[:200]
        elif detect_language(text) == 'en':
            zh, tags = translate_full_article(text)
            script_content = f"{zh}\n\n---\n\n{text}" if zh else text
            script_url = save_script(title, script_content)
            first_para = next((p.strip() for p in zh.split("\n") if len(p.strip()) > 20), "")
            summary = first_para[:200]
        else:
            tags = gen_tags(title, text[:3000])
            script_url = save_script(title, text)
            first_para = next((p.strip() for p in text.split("\n") if len(p.strip()) > 20), "")
            summary = first_para[:200]
        article_id = add_article(
            title=title,
            source_url=item["url"],
            source_type="url",
            summary=summary,
            image_url=image_url_extracted,
            word_count=len(text or ""),
            article_md_path=script_url,
        )
        if tags:
            update_tags(article_id, tags)
        threading.Thread(target=_remember_in_bg, args=(article_id,), daemon=True).start()
        return article_id

    try:
        article_id = await asyncio.to_thread(_save)
    except Exception as e:
        update_feed_item_status(item_id, "pending")
        print(f"[inbox] save error for {item['url']}: {e}")
        return JSONResponse({"ok": False, "error": "入库失败，请稍后重试"}, status_code=500)
    return JSONResponse({"ok": True, "article_id": article_id, "title": item["title"]})


@app.post("/api/inbox/{item_id}/dismiss")
async def api_inbox_dismiss(item_id: str):
    update_feed_item_status(item_id, "dismissed")
    return JSONResponse({"ok": True})


# ── Publish ───────────────────────────────────────────────────────────────────

@app.post("/publish")
async def publish_to_pages():
    pages_url = os.getenv("GITHUB_PAGES_URL", "").rstrip("/")
    if not pages_url:
        return JSONResponse({"ok": False, "error": "GITHUB_PAGES_URL 未在 .env 中配置"}, status_code=400)
    try:
        result = subprocess.run(
            [sys.executable, "scripts/publish_to_pages.py"],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            return JSONResponse({"ok": False, "error": result.stderr or result.stdout})
        rss_url = f"{pages_url}/podcast.xml"
        return JSONResponse({"ok": True, "rss_url": rss_url, "log": result.stdout})
    except subprocess.TimeoutExpired:
        return JSONResponse({"ok": False, "error": "发布超时，请检查网络连接"}, status_code=500)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job = db.get_podcast_job(job_id)
    if not job:
        return JSONResponse({"status": "not_found", "message": "任务不存在"})
    return JSONResponse({
        "id": job["id"],
        "status": job["status"],
        "stage": job["stage"],
        "message": job["message"],
        "files": job["files"],
        "result": job["result"],
        "error_code": job["error_code"],
        "error_message": job["error_message"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
    })


@app.post("/api/podcast-jobs/{job_id}/retry-publish")
async def retry_podcast_job_publish(job_id: str):
    from services import podcast_jobs
    result = await asyncio.to_thread(podcast_jobs.retry_publish, job_id)
    return JSONResponse(result, status_code=200 if result.get("ok") else 400)


@app.post("/generate/url")
async def generate_from_url(
    background_tasks: BackgroundTasks,
    request: Request,
    url: str = Form(...),
    title: str = Form(""),
    voice: str = Form("zh-CN-YunxiNeural"),
    use_original_audio: bool = Form(False),
    summarize: bool = Form(False),
    force_transcribe: bool = Form(False),
):
    from services import podcast_jobs
    source_type = detect_url_platform(url)
    base_url = str(request.base_url).rstrip('/')
    job_id = podcast_jobs.enqueue(url, source_type, {
        "title": title,
        "base_url": base_url,
        "voice": voice,
        "use_original_audio": use_original_audio,
        "summarize": summarize,
        "force_transcribe": force_transcribe,
    })
    return JSONResponse({"job_id": job_id})


@app.post("/generate/file")
async def generate_from_file(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    voice: str = Form("zh-CN-YunxiNeural"),
    summarize: bool = Form(False),
):
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    from services import podcast_jobs
    source_type = 'pdf' if file.filename.lower().endswith('.pdf') else 'txt'
    base_url = str(request.base_url).rstrip('/')
    job_id = podcast_jobs.enqueue(temp_path, source_type, {
        "title": title,
        "base_url": base_url,
        "voice": voice,
        "use_original_audio": False,
        "summarize": summarize,
    })
    return JSONResponse({"job_id": job_id})
