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
        log.error(f"[agent] feed sync error: {e}")


async def task_embed_stale():
    """After sync: generate embeddings for new brain pages (needs OPENAI_API_KEY)."""
    await asyncio.to_thread(memory.embed_stale)


async def task_daily_brief():
    """07:00 daily: agent自主决定今日简报内容并写回大脑。"""
    log.info("[agent] running daily brief via agent loop...")
    try:
        from services.agent_loop import run as agent_run
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        prompt = (
            f"今天是 {today}。请查看最近的文章，找出有意思的联系和洞察，"
            f"写一篇今日知识简报（300-500字），然后用 write_insight 保存到大脑，slug 用 daily-{today}。"
        )
        result = await asyncio.to_thread(
            lambda: next(agent_run(prompt, stream=True), "")
        )
        log.info(f"[agent] daily brief done: {result[:80]}")
    except Exception as e:
        log.error(f"[agent] daily brief error: {e}")


async def task_weekly_synthesis():
    """Monday 08:00: agent自主综合本周知识，写洞察。"""
    log.info("[agent] running weekly synthesis via agent loop...")
    try:
        from services.agent_loop import run as agent_run
        week = datetime.now(timezone.utc).strftime("%Y-W%W")
        prompt = (
            f"现在是第 {week} 周末。请获取大脑统计信息和最近文章，"
            f"选出最值得深挖的2-3个主题，对每个主题调用 synthesize 综合分析，"
            f"然后用 write_insight 将每个综合洞察写回大脑。"
        )
        result = await asyncio.to_thread(
            lambda: next(agent_run(prompt, stream=True), "")
        )
        log.info(f"[agent] weekly synthesis done: {result[:80]}")
    except Exception as e:
        log.error(f"[agent] weekly synthesis error: {e}")


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
        log.error(f"[agent] backfill error: {e}")


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
