"""
Agent task queue and evolution log.

This is intentionally lightweight: SQLite is the queue, APScheduler triggers a
small worker, and every autonomous action records an audit-friendly log entry.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from services import db, memory

log = logging.getLogger("agent_tasks")

MAX_ATTEMPTS = 3
RETRY_DELAY_MINUTES = 10
STALE_RUNNING_MINUTES = 45


def enqueue_article_evolution(article_id: str) -> list[str]:
    """Create the default autonomous tasks for a newly saved article."""
    article = db.get_article(article_id)
    if not article:
        return []
    title = article.get("title") or "未命名文章"
    task_ids = [
        db.enqueue_agent_task(
            "digest_article",
            f"消化文章：《{title}》",
            {"article_id": article_id},
            priority=80,
        ),
        db.enqueue_agent_task(
            "connect_article",
            f"连接文章：《{title}》",
            {"article_id": article_id},
            priority=60,
        ),
    ]
    db.add_evolution_log(
        "task_created",
        f"为《{title}》创建了消化和连接任务。",
        artifact_type="article",
        artifact_id=article_id,
        after={"task_ids": task_ids},
    )
    return task_ids


def enqueue_highlight_analysis(article_id: str, highlight_text: str) -> str:
    """Queue an agent analysis task for a user highlight."""
    article = db.get_article(article_id)
    title = (article.get("title") or "未知文章") if article else "未知文章"
    task_id = db.enqueue_agent_task(
        "analyze_highlight",
        f"分析高亮：《{title}》",
        {"article_id": article_id, "text": highlight_text},
        priority=90,  # higher than article tasks — user signal
    )
    db.add_evolution_log(
        "task_created",
        f"用户高亮触发分析任务：《{title}》",
        artifact_type="article",
        artifact_id=article_id,
    )
    return task_id


def run_next() -> dict | None:
    """Run one pending task. Safe to call from a scheduler."""
    reset_count = db.reset_stale_agent_tasks(timeout_minutes=STALE_RUNNING_MINUTES)
    if reset_count:
        db.add_evolution_log(
            "task_recovered",
            f"发现 {reset_count} 个运行超时的任务，已自动放回队列。",
        )
    task = db.get_next_agent_task()
    if not task:
        return None
    return _run_task(task)


def _run_task(task: dict) -> dict:
    task_id = task["id"]
    attempts = int(task.get("attempts") or 0) + 1
    now = datetime.now(timezone.utc).isoformat()
    db.update_agent_task(
        task_id,
        status="running",
        attempts=attempts,
        started_at=now,
        finished_at=None,
        error=None,
    )
    db.add_evolution_log(
        "task_started",
        f"开始执行：{task['title']}（第 {attempts}/{MAX_ATTEMPTS} 次）",
        task_id=task_id,
    )

    try:
        handler = HANDLERS.get(task["type"])
        if not handler:
            raise ValueError(f"未知任务类型：{task['type']}")
        payload = json.loads(task.get("payload_json") or "{}")
        result = handler(task, payload)
        db.update_agent_task(
            task_id,
            status="done",
            finished_at=datetime.now(timezone.utc).isoformat(),
            result_json=json.dumps(result or {}, ensure_ascii=False),
        )
        db.add_evolution_log(
            "task_completed",
            f"完成任务：{task['title']}",
            task_id=task_id,
            after=result or {},
        )
        return {"ok": True, "task_id": task_id, "result": result}
    except Exception as exc:
        log.exception("task failed: %s", task_id)
        error = str(exc)
        if attempts < MAX_ATTEMPTS:
            scheduled_at = (datetime.now(timezone.utc) + timedelta(minutes=RETRY_DELAY_MINUTES)).isoformat()
            db.update_agent_task(
                task_id,
                status="pending",
                scheduled_at=scheduled_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
                error=error,
            )
            db.add_evolution_log(
                "task_retry_scheduled",
                f"任务失败，将在 {RETRY_DELAY_MINUTES} 分钟后重试：{task['title']}。原因：{error}",
                task_id=task_id,
            )
            return {
                "ok": False,
                "task_id": task_id,
                "retry": True,
                "attempts": attempts,
                "error": error,
            }

        db.update_agent_task(
            task_id,
            status="failed",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=error,
        )
        db.add_evolution_log(
            "task_failed",
            f"任务最终失败：{task['title']}。原因：{error}",
            task_id=task_id,
        )
        return {"ok": False, "task_id": task_id, "retry": False, "attempts": attempts, "error": error}


def run_task_now(task_id: str) -> dict:
    """Mark a task runnable and execute it immediately if possible."""
    task = db.get_agent_task(task_id)
    if not task:
        return {"ok": False, "error": "task not found"}
    if task["status"] == "running":
        return {"ok": False, "error": "task already running"}
    db.update_agent_task(task_id, status="pending", scheduled_at=datetime.now(timezone.utc).isoformat())
    task = db.get_agent_task(task_id)
    return _run_task(task)


def _read_article_content(article: dict, max_chars: int = 8000) -> str:
    path = (article.get("article_md_path") or "").lstrip("/")
    if not path:
        return article.get("summary") or ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()[:max_chars]
    except FileNotFoundError:
        return article.get("summary") or ""


def _tags(article: dict) -> list[str]:
    tags = article.get("tags") or []
    if isinstance(tags, str):
        try:
            return json.loads(tags)
        except Exception:
            return []
    return tags if isinstance(tags, list) else []


def digest_article(task: dict, payload: dict) -> dict:
    """Summarize the article's state and fill low-risk metadata."""
    article_id = payload["article_id"]
    article = db.get_article(article_id)
    if not article:
        raise ValueError("article not found")

    content = _read_article_content(article)
    tags_before = _tags(article)
    tags_after = tags_before
    tag_summary = "保留现有标签。"

    if not tags_before and content:
        from services.llm import generate_tags

        generated = generate_tags(article["title"], content[:2000]) or []
        if generated:
            tags_after = generated
            db.update_tags(article_id, generated)
            tag_summary = f"新增标签：{', '.join(generated[:6])}"

    core_points = _extract_bullet_points(content)
    result = {
        "article_id": article_id,
        "title": article["title"],
        "tags_before": tags_before,
        "tags_after": tags_after,
        "core_points": core_points,
        "content_sample_chars": len(content),
    }
    db.add_evolution_log(
        "article_digest",
        f"消化《{article['title']}》：{tag_summary} 提炼 {len(core_points)} 条候选观点。",
        task_id=task["id"],
        before={"tags": tags_before},
        after={"tags": tags_after, "core_points": core_points},
        artifact_type="article",
        artifact_id=article_id,
    )
    return result


def connect_article(task: dict, payload: dict) -> dict:
    """Deep cross-reference via ReAct agent loop — replaces simple recall+log."""
    article_id = payload["article_id"]
    article = db.get_article(article_id)
    if not article:
        raise ValueError("article not found")

    title = article.get("title", "未知标题")
    summary = (article.get("summary") or "")[:500]
    tags = _tags(article)

    if not summary:
        result = {"skipped": True, "reason": "no summary"}
        db.add_evolution_log(
            "article_connected",
            f"《{title}》无摘要，跳过深度关联分析。",
            task_id=task["id"],
            artifact_type="article",
            artifact_id=article_id,
        )
        return result

    from services.agent_loop import run as agent_run
    slug = f"insight-{article_id[:8]}"
    prompt = (
        f"刚刚入库了一篇新文章：《{title}》\n"
        f"标签：{json.dumps(tags, ensure_ascii=False)}\n"
        f"摘要：{summary}\n\n"
        f"请完成以下任务：\n"
        f"1. 用 recall 在大脑中搜索与这篇文章相关的已有知识（至少搜索2个不同角度）\n"
        f"2. 找出这篇文章与已有知识之间最有价值的联系或对比\n"
        f"3. 提炼出1-2条真正有洞察力的结论，用 write_insight 写回大脑（slug 用 {slug}）\n"
        f"4. 最后用一句话总结：这篇文章为大脑补充了什么新视角\n\n"
        f"不要复述文章内容，专注于跨文章的联系和新发现。"
    )

    analysis = agent_run(prompt, max_steps=10)

    # Write analysis back to article insights
    existing = article.get("insights") or {}
    if isinstance(existing, str):
        try:
            existing = json.loads(existing)
        except Exception:
            existing = {}
    existing["agent_analysis"] = analysis[:800]
    db.update_insights(article_id, existing)

    db.add_evolution_log(
        "article_connected",
        f"ReAct 完成《{title}》的深度关联分析，洞察已写入大脑。",
        task_id=task["id"],
        after={"analysis_preview": analysis[:200]},
        artifact_type="article",
        artifact_id=article_id,
    )
    return {"article_id": article_id, "analysis_preview": analysis[:200]}


def _extract_bullet_points(text: str, limit: int = 3) -> list[str]:
    points = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ", "• ")):
            points.append(line[2:].strip())
        elif line.startswith("## "):
            points.append(line[3:].strip())
        if len(points) >= limit:
            break
    if points:
        return points

    compact = " ".join(text.split())
    if not compact:
        return []
    chunks = [p.strip() for p in compact.replace("。", "。\n").splitlines() if len(p.strip()) > 18]
    return chunks[:limit]


def analyze_highlight(task: dict, payload: dict) -> dict:
    """Agent reacts to a user highlight — strongest signal of importance."""
    article_id = payload["article_id"]
    highlight_text = payload["text"]
    article = db.get_article(article_id)
    if not article:
        raise ValueError("article not found")

    title = article.get("title", "未知文章")

    from services.agent_loop import run as agent_run
    prompt = (
        f"用户在《{title}》中高亮了以下内容，这是用户认为重要的强信号：\n\n"
        f"「{highlight_text}」\n\n"
        f"请完成：\n"
        f"1. 用 recall 搜索大脑中与这段内容相关的知识（1-2次）\n"
        f"2. 分析这段高亮在整个知识体系中的意义：是验证了已有观点？还是带来了新视角？还是与某篇文章形成对照？\n"
        f"3. 如果发现有价值的连接，用 write_insight 写一条简短洞察（slug: highlight-{article_id[:8]}）\n"
        f"4. 用1-2句话回答：这段高亮为什么重要？"
    )

    analysis = agent_run(prompt, max_steps=6)

    # Append to article's highlight_analyses list
    existing = article.get("insights") or {}
    if isinstance(existing, str):
        try:
            existing = json.loads(existing)
        except Exception:
            existing = {}
    analyses = existing.get("highlight_analyses", [])
    analyses.append({"text": highlight_text[:200], "analysis": analysis[:400]})
    existing["highlight_analyses"] = analyses[-10:]  # keep latest 10
    db.update_insights(article_id, existing)

    db.add_evolution_log(
        "highlight_analyzed",
        f"分析《{title}》中的高亮：「{highlight_text[:60]}…」",
        task_id=task["id"],
        after={"analysis_preview": analysis[:150]},
        artifact_type="article",
        artifact_id=article_id,
    )
    return {"article_id": article_id, "analysis_preview": analysis[:150]}


HANDLERS = {
    "digest_article": digest_article,
    "connect_article": connect_article,
    "analyze_highlight": analyze_highlight,
}
