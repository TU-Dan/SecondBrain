"""
Autonomous agent — event-driven scheduler.
Triggers agent_loop.run() for reasoning tasks instead of hardcoded logic.
"""

import asyncio
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from services import db, memory
from services.feeds import refresh_all_feeds

log = logging.getLogger("agent")

_scheduler: AsyncIOScheduler | None = None


# ── Scheduled tasks ──────────────────────────────────────────────────────────

async def task_sync_feeds():
    """Hourly: fetch all RSS feeds and score new items."""
    log.info("[agent] syncing feeds...")
    try:
        added = await refresh_all_feeds()
        count = db.count_inbox()
        log.info(f"[agent] feed sync done. new: {added}, inbox: {count}")
    except Exception as e:
        log.exception("[agent] feed sync error")
        db.add_evolution_log("scheduler_failed", f"RSS 同步失败：{e}")


async def task_embed_stale():
    """After sync: generate embeddings for new brain pages (needs OPENAI_API_KEY)."""
    try:
        ok = await asyncio.to_thread(memory.embed_stale)
        if ok:
            log.info("[agent] embedded stale brain pages")
    except Exception as e:
        log.exception("[agent] embed stale error")
        db.add_evolution_log("scheduler_failed", f"大脑向量索引更新失败：{e}")


async def task_daily_brief():
    """07:00 daily: agent自主决定今日简报内容并写回大脑。"""
    log.info("[agent] running daily brief via agent loop...")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        from services.agent_loop import run as agent_run
        prompt = (
            f"今天是 {today}。请查看最近的文章，找出有意思的联系和洞察，"
            f"写一篇今日知识简报（300-500字），然后用 write_insight 保存到大脑，slug 用 daily-{today}。"
        )
        db.add_evolution_log("scheduler_started", f"开始生成 {today} 今日知识简报。")
        result = await asyncio.to_thread(agent_run, prompt, None, 8, False)
        db.add_evolution_log(
            "scheduler_completed",
            f"{today} 今日知识简报生成完成。",
            after={"preview": result[:240]},
        )
        log.info(f"[agent] daily brief done: {result[:80]}")
    except Exception as e:
        log.exception("[agent] daily brief error")
        db.add_evolution_log("scheduler_failed", f"{today} 今日知识简报失败：{e}")


async def task_weekly_synthesis():
    """Monday 08:00: agent自主综合本周知识，写洞察。"""
    log.info("[agent] running weekly synthesis via agent loop...")
    week = datetime.now(timezone.utc).strftime("%Y-W%W")
    try:
        from services.agent_loop import run as agent_run
        prompt = (
            f"现在是第 {week} 周末。请获取大脑统计信息和最近文章，"
            f"选出最值得深挖的2-3个主题，对每个主题调用 synthesize 综合分析，"
            f"然后用 write_insight 将每个综合洞察写回大脑。"
        )
        db.add_evolution_log("scheduler_started", f"开始生成 {week} 每周知识综合。")
        result = await asyncio.to_thread(agent_run, prompt, None, 8, False)
        db.add_evolution_log(
            "scheduler_completed",
            f"{week} 每周知识综合生成完成。",
            after={"preview": result[:240]},
        )
        log.info(f"[agent] weekly synthesis done: {result[:80]}")
    except Exception as e:
        log.exception("[agent] weekly synthesis error")
        db.add_evolution_log("scheduler_failed", f"{week} 每周知识综合失败：{e}")


async def task_sync_unindexed_articles():
    """Sync any articles in DB that aren't yet in GBrain memory."""
    try:
        articles = db.list_articles(limit=200)
        count = 0
        for article in articles:
            if article.get("summary") or article.get("insights"):
                ok = await asyncio.to_thread(memory.remember, article)
                if ok:
                    count += 1
        if count:
            log.info(f"[agent] backfilled {count} articles into GBrain")
    except Exception as e:
        log.exception("[agent] backfill error")
        db.add_evolution_log("scheduler_failed", f"大脑文章回填失败：{e}")


async def task_run_agent_queue():
    """Run one queued autonomous evolution task."""
    try:
        from services import agent_tasks
        result = await asyncio.to_thread(agent_tasks.run_next)
        if result:
            log.info(f"[agent] task queue result: {result}")
    except Exception as e:
        log.exception("[agent] task queue error")
        db.add_evolution_log("scheduler_failed", f"Agent 任务队列执行失败：{e}")


# ── Scheduler lifecycle ───────────────────────────────────────────────────────

def start():
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

    # Hourly: RSS sync
    _scheduler.add_job(task_sync_feeds, "interval", hours=1, id="sync_feeds",
                       next_run_time=datetime.now())

    # After each sync: embed new content (no-op without OpenAI key)
    _scheduler.add_job(task_embed_stale, "interval", hours=1, id="embed_stale",
                       minutes=5)

    # Every few minutes: run one autonomous task from the queue.
    _scheduler.add_job(task_run_agent_queue, "interval", minutes=3, id="agent_task_queue",
                       next_run_time=datetime.now())

    # Daily 07:00: brief
    _scheduler.add_job(task_daily_brief, CronTrigger(hour=7, minute=0),
                       id="daily_brief")

    # Monday 08:00: weekly synthesis
    _scheduler.add_job(task_weekly_synthesis,
                       CronTrigger(day_of_week="mon", hour=8, minute=0),
                       id="weekly_synthesis")

    _scheduler.start()
    log.info("[agent] scheduler started")

    # Backfill existing articles into GBrain on startup
    loop = asyncio.get_event_loop()
    loop.create_task(task_sync_unindexed_articles())


def stop():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("[agent] scheduler stopped")
