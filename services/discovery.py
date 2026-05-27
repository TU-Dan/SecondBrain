"""
Daily Discovery — proactively search the web based on user interests.

Requires SERPER_API_KEY in .env  (https://serper.dev, free 2500/month)
"""

import json
import logging
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone

from services.db import list_all_tags, add_inbox_item, get_conn
from services.llm import _get_client

log = logging.getLogger("discovery")

MIN_SCORE    = 55   # lowered: 68 was filtering out too much
MAX_TAGS     = 5
RESULTS_PER_QUERY = 8


# ── Helpers ───────────────────────────────────────────────────────────────────

def _already_seen(url: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM inbox_items WHERE url=? "
            "UNION ALL SELECT 1 FROM articles WHERE source_url=? LIMIT 1",
            (url, url),
        ).fetchone()
    return row is not None


def _search(query: str, num: int = RESULTS_PER_QUERY) -> list[dict]:
    """
    Call Serper.dev via stdlib urllib — no curl_cffi, no threading quirks.
    Reads SERPER_API_KEY fresh every call to avoid module-load-order issues.
    """
    key = os.getenv("SERPER_API_KEY")
    if not key:
        log.warning("[discovery] SERPER_API_KEY not set")
        return []

    payload = json.dumps({
        "q": query,
        "num": num,
        "gl": "cn",
        "hl": "zh-cn",
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=payload,
        headers={
            "X-API-KEY": key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [
            {
                "title": item.get("title", "").strip(),
                "url":   item.get("link",  "").strip(),
                "description": item.get("snippet", "").strip(),
            }
            for item in data.get("organic", [])
            if item.get("link") and item.get("title")
        ]
    except Exception as e:
        log.warning(f"[discovery] search error for '{query}': {e}")
        return []


def _score_items(items: list[dict], user_tags: list[str], topic: str) -> list[int]:
    """Score items 0-100 via LLM. Falls back to 60 on any error."""
    client = _get_client()
    if not client or not items:
        return [60] * len(items)

    items_str = "\n".join(
        f"{i+1}. {it['title']}: {it['description'][:100]}"
        for i, it in enumerate(items)
    )
    prompt = (
        f"用户兴趣：{'、'.join(user_tags[:15])}\n"
        f"搜索主题：{topic}\n\n"
        f"对以下结果打分（0-100）。高分：深度内容、独特观点、近期发布。"
        f"低分：广告、导航页、电商。\n"
        f"只返回JSON整数数组，如[85,20,72]，不要其他文字：\n\n{items_str}"
    )
    try:
        resp = _get_client().chat.completions.create(
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
                scores.append(60)
            return [max(0, min(100, int(s))) for s in scores[:len(items)]]
    except Exception as e:
        log.warning(f"[discovery] score error: {e}")
    return [60] * len(items)


# ── Main ──────────────────────────────────────────────────────────────────────

def run_discovery_sync() -> dict:
    """
    Run one discovery cycle. Returns:
      {ok, added, tags_searched, items, steps}
    'steps' is a debug log of what happened at each stage.
    """
    steps = []

    key = os.getenv("SERPER_API_KEY")
    if not key:
        return {"ok": False, "reason": "SERPER_API_KEY 未配置", "added": 0, "items": [], "steps": ["❌ SERPER_API_KEY 未设置"]}

    steps.append("✓ SERPER_API_KEY 已加载")

    tags = list_all_tags()
    if not tags:
        return {"ok": False, "reason": "知识库暂无标签", "added": 0, "items": [], "steps": steps + ["❌ 知识库无标签"]}

    top_tags  = [t["tag"] for t in tags[:MAX_TAGS]]
    all_tags  = [t["tag"] for t in tags[:20]]
    steps.append(f"✓ 用户标签：{top_tags}")

    added_items: list[dict] = []
    total_added = 0

    for tag in top_tags:
        queries = [
            f"{tag} 深度解析 OR 教程 OR 趋势",
            f"{tag} analysis OR guide OR trends 2025",
        ]
        seen_this_tag: set[str] = set()

        for query in queries:
            raw = _search(query)
            steps.append(f"🔍 [{tag}] '{query}' → {len(raw)} 条原始结果")

            fresh = [
                r for r in raw
                if r["url"] and r["url"] not in seen_this_tag and not _already_seen(r["url"])
            ]
            skipped = len(raw) - len(fresh)
            if skipped:
                steps.append(f"   ↳ 跳过 {skipped} 条（已存在）")

            if not fresh:
                steps.append("   ↳ 无新内容")
                continue

            scores = _score_items(fresh, all_tags, tag)
            passed = [(item, score) for item, score in zip(fresh, scores) if score >= MIN_SCORE]
            steps.append(f"   ↳ 评分后通过 {len(passed)}/{len(fresh)}（阈值 {MIN_SCORE}）")

            for item, score in passed:
                seen_this_tag.add(item["url"])
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
                steps.append(f"   ✓ 已加入收件箱（{score}分）：{item['title'][:50]}")

    steps.append(f"完成：共新增 {total_added} 条")
    return {
        "ok": True,
        "added": total_added,
        "tags_searched": top_tags,
        "items": added_items,
        "steps": steps,
    }


async def run_daily_discovery() -> dict:
    import asyncio
    return await asyncio.to_thread(run_discovery_sync)
