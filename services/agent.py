"""
Autonomous agent loop.
Runs on a schedule: hourly RSS sync, daily brief, weekly synthesis.
All compounding into GBrain memory.
"""

import asyncio
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from services import db, memory, llm
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
    """07:00 daily: pull recent articles from brain, synthesize brief, save back."""
    log.info("[agent] generating daily brief...")
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        recent = db.list_articles(limit=20)
        if not recent:
            return

        # Build context from recent articles
        brief_text = await asyncio.to_thread(llm.generate_daily_brief, recent[:10])
        if brief_text:
            slug = f"daily-{today}"
            memory.write_page(slug, f"每日简报 {today}", brief_text, subdir="daily")
            log.info(f"[agent] daily brief saved: {slug}")
    except Exception as e:
        log.error(f"[agent] daily brief error: {e}")


async def task_weekly_synthesis():
    """Monday 08:00: synthesize cross-article insights from past week."""
    log.info("[agent] running weekly synthesis...")
    try:
        recent = db.list_articles(limit=50)
        if len(recent) < 3:
            return

        all_tags: dict[str, int] = {}
        for a in recent:
            import json
            try:
                for t in json.loads(a.get("tags") or "[]"):
                    all_tags[t] = all_tags.get(t, 0) + 1
            except Exception:
                pass

        top_topics = sorted(all_tags, key=lambda t: -all_tags[t])[:5]

        for topic in top_topics:
            synthesis = await asyncio.to_thread(memory.synthesize, topic)
            if synthesis:
                slug = f"synthesis-{topic}-{datetime.now(timezone.utc).strftime('%Y-W%W')}"
                memory.write_page(slug, f"综合洞察：{topic}", synthesis, subdir="insights")
                log.info(f"[agent] synthesis saved: {slug}")
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
