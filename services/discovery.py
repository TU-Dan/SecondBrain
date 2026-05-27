"""
Daily Discovery — proactively search the web based on user interests.

Requires SERPER_API_KEY in environment (.env).
Sign up free at https://serper.dev — 2500 queries/month on free tier.

Flow:
  1. Read user's top N tags from library
  2. For each tag, run 2 searches (CN + EN)
  3. LLM scores results by relevance + quality
  4. High-scoring, unseen items → inbox
"""

import json
import logging
import os
import re
from datetime import datetime, timezone

from curl_cffi import requests as cffi_requests

from services.db import list_all_tags, add_inbox_item, get_conn
from services.llm import _get_client

log = logging.getLogger("discovery")

# ── Config ────────────────────────────────────────────────────────────────────

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
MIN_SCORE = 68        # Items below this threshold are dropped
MAX_TAGS = 5          # How many top tags to search per run
RESULTS_PER_QUERY = 8 # Serper results per query


# ── Helpers ───────────────────────────────────────────────────────────────────

def _already_seen(url: str) -> bool:
    """Return True if URL already exists in inbox or library."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM inbox_items WHERE url=? "
            "UNION ALL SELECT 1 FROM articles WHERE url=? LIMIT 1",
            (url, url),
        ).fetchone()
    return row is not None


def _search(query: str, num: int = RESULTS_PER_QUERY) -> list[dict]:
    """Call Serper.dev Google Search API. Returns list of {title, url, description}."""
    if not SERPER_API_KEY:
        return []
    try:
        resp = cffi_requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_API_KEY},
            json={"q": query, "num": num, "gl": "cn", "hl": "zh-cn"},
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "title": item.get("title", "").strip(),
                "url": item.get("link", "").strip(),
                "description": item.get("snippet", "").strip(),
            }
            for item in data.get("organic", [])
            if item.get("link") and item.get("title")
        ]
    except Exception as e:
        log.warning(f"[discovery] search failed for '{query}': {e}")
        return []


def _score_items(items: list[dict], user_tags: list[str], topic: str) -> list[int]:
    """
    Use LLM to score each result 0-100.
    High: deep analysis, tutorials, unique insight, recent.
    Low: ads, nav pages, ecommerce, duplicate titles.
    """
    client = _get_client()
    if not client or not items:
        return [50] * len(items)

    interest_str = "、".join(user_tags[:15])
    items_str = "\n".join(
        f"{i+1}. {it['title']}: {it['description'][:100]}"
        for i, it in enumerate(items)
    )
    prompt = (
        f"用户兴趣标签：{interest_str}\n"
        f"当前搜索主题：{topic}\n\n"
        f"对以下搜索结果打综合分（相关性 × 内容质量，0-100整数）。\n"
        f"高分：深度分析、教程、独特观点、近期发布。\n"
        f"低分：广告、导航页、电商、标题党、与主题无关。\n"
        f"只返回JSON整数数组，如 [85,20,72]，不要其他任何文字：\n\n"
        f"{items_str}"
    )
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        text = resp.choices[0].message.content.strip()
        m = re.search(r'\[[\d,\s]+\]', text)
        if m:
            scores = json.loads(m.group())
            while len(scores) < len(items):
                scores.append(50)
            return [max(0, min(100, int(s))) for s in scores[:len(items)]]
    except Exception as e:
        log.warning(f"[discovery] score error: {e}")
    return [50] * len(items)


# ── Main ──────────────────────────────────────────────────────────────────────

def run_discovery_sync() -> dict:
    """
    Synchronous entry point — call via asyncio.to_thread from async context.
    Returns: {ok, added, tags_searched, items, reason?}
    """
    if not SERPER_API_KEY:
        log.warning("[discovery] SERPER_API_KEY not set — skipping.")
        return {"ok": False, "reason": "SERPER_API_KEY 未配置", "added": 0, "items": []}

    tags = list_all_tags()
    if not tags:
        return {"ok": False, "reason": "知识库暂无标签", "added": 0, "items": []}

    top_tags = [t["tag"] for t in tags[:MAX_TAGS]]
    all_tags = [t["tag"] for t in tags[:20]]
    total_added = 0
    added_items: list[dict] = []

    log.info(f"[discovery] searching for tags: {top_tags}")

    for tag in top_tags:
        # Two queries per tag: Chinese and English
        queries = [
            f"{tag} 深度解析 OR 教程 OR 趋势",
            f"{tag} in-depth analysis OR guide OR trends 2025",
        ]
        seen_this_tag: set[str] = set()

        for query in queries:
            results = _search(query)

            # Deduplicate: skip URLs already in inbox/library or seen this run
            fresh = [
                r for r in results
                if r["url"]
                and r["url"] not in seen_this_tag
                and not _already_seen(r["url"])
            ]
            if not fresh:
                continue

            scores = _score_items(fresh, all_tags, tag)

            for item, score in zip(fresh, scores):
                seen_this_tag.add(item["url"])
                if score >= MIN_SCORE:
                    add_inbox_item(
                        title=item["title"],
                        url=item["url"],
                        intent="read",
                        description=item.get("description", ""),
                        note=f"AI 发现 · {tag}",
                        source="discovery",
                        priority="normal",
                    )
                    total_added += 1
                    added_items.append({
                        "title": item["title"],
                        "url": item["url"],
                        "description": item.get("description", ""),
                        "tag": tag,
                        "score": score,
                    })
                    log.info(
                        f"[discovery] added (score={score}): {item['title'][:60]}"
                    )

    log.info(f"[discovery] run complete. added={total_added}")
    return {
        "ok": True,
        "added": total_added,
        "tags_searched": top_tags,
        "items": added_items,
    }


async def run_daily_discovery() -> dict:
    """Async wrapper — runs sync discovery in a thread pool."""
    import asyncio
    return await asyncio.to_thread(run_discovery_sync)
