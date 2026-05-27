"""
Daily Discovery — three content sources:

1. Serper web search  (domain-whitelist filtered)
2. Custom curated pages  (aihot.virxact.com/daily, etc.)

Requires SERPER_API_KEY in .env  →  https://serper.dev  (free 2500/month)
"""

import json
import logging
import os
import re
import urllib.request
from urllib.parse import urlparse

from curl_cffi import requests as cffi_requests

from services.db import list_all_tags, add_inbox_item, get_conn
from services.llm import _get_client

log = logging.getLogger("discovery")

# ── Thresholds ────────────────────────────────────────────────────────────────

MIN_SCORE_TRUSTED = 50   # trusted domain  → relaxed
MIN_SCORE_UNKNOWN = 72   # unknown domain  → strict


# ── Domain lists ─────────────────────────────────────────────────────────────

TRUSTED_DOMAINS = frozenset({
    # 中文通用
    "zhihu.com", "zhuanlan.zhihu.com",
    "sspai.com", "huxiu.com", "36kr.com",
    "geekpark.net", "ruanyifeng.com",
    "ithome.com", "infoq.cn", "juejin.cn",
    # 中文财经
    "wallstreetcn.com", "caixin.com", "yicai.com",
    "cls.cn", "jiemian.com", "gelonghui.com", "ftchinese.com",
    # 英文通用
    "paulgraham.com", "fs.blog", "lesswrong.com",
    "hbr.org", "jamesclear.com", "waitbutwhy.com",
    "aeon.co", "wired.com", "theatlantic.com",
    "the-decoder.com", "theverge.com", "techcrunch.com",
    # AI 专项
    "arxiv.org", "hai.stanford.edu", "mckinsey.com",
    "anthropic.com", "openai.com", "huggingface.co",
    "deepmind.google", "runwayml.com", "microsoft.com",
    # 英文财经
    "economist.com", "ft.com", "bloomberg.com",
    "wsj.com", "marketwatch.com",
})

BLOCKED_DOMAINS = frozenset({
    "youtube.com", "youtu.be",
    "facebook.com", "twitter.com", "x.com", "t.co",
    "instagram.com", "tiktok.com", "weibo.com",
    "reddit.com",
    "amazon.com", "jd.com", "taobao.com", "tmall.com",
    # known junk from previous runs
    "nike.com", "phrase.com", "churnzero.com",
    "blog.marketingblatt.com", "xsc.gsau.edu.cn",
})


# ── Custom curated sources ────────────────────────────────────────────────────
# These are hand-picked pages that already aggregate quality links.
# We scrape them directly instead of going through Serper.

CUSTOM_SOURCES = [
    {
        "url": "https://aihot.virxact.com/daily",
        "name": "AI HOT 日报",
        "tag": "人工智能",
        # Skip social media links from this source — we can't read X/Twitter
        "skip_domains": {"x.com", "twitter.com", "t.co"},
    },
]

# ── Tag → query templates ─────────────────────────────────────────────────────
# Avoids generic keyword soup. Finance gets its own trusted-site queries
# (substitute for tophub.today/c/finance which blocks scrapers).

_FINANCE_TAGS = {"财经", "金融", "投资", "股市", "经济", "宏观", "理财"}
_AI_TAGS      = {"AI", "人工智能", "机器学习", "大模型", "LLM", "深度学习"}


def _queries_for_tag(tag: str) -> list[str]:
    if any(k in tag for k in _FINANCE_TAGS):
        return [
            f"{tag} 分析 OR 研报 OR 解读",
            f"{tag} analysis OR outlook site:economist.com OR site:ft.com OR site:bloomberg.com",
        ]
    if any(k in tag for k in _AI_TAGS):
        return [
            f"{tag} 解析 OR 研究 OR 进展",
            f"{tag} research OR paper site:arxiv.org OR site:the-decoder.com OR site:anthropic.com",
        ]
    # personal growth / general
    return [
        f"{tag} 深度 OR 方法论 OR 实践",
        f"{tag} guide OR essay site:fs.blog OR site:jamesclear.com OR site:hbr.org",
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _already_seen(url: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM inbox_items WHERE url=? "
            "UNION ALL SELECT 1 FROM articles WHERE source_url=? LIMIT 1",
            (url, url),
        ).fetchone()
    return row is not None


def _serper_search(query: str, num: int = 8) -> list[dict]:
    key = os.getenv("SERPER_API_KEY")
    if not key:
        return []
    payload = json.dumps({"q": query, "num": num, "gl": "cn", "hl": "zh-cn"}).encode()
    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=payload,
        headers={"X-API-KEY": key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
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
        log.warning(f"[discovery] serper error for '{query}': {e}")
        return []


def _score_items(items: list[dict], user_tags: list[str], topic: str) -> list[int]:
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
        f"低分：广告、导航页、电商、与主题无关。\n"
        f"只返回JSON整数数组，如[85,20,72]，不要其他文字：\n\n{items_str}"
    )
    try:
        resp = _get_client().chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=200,
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


# ── Source 1: Serper with domain filtering ────────────────────────────────────

def _run_serper(top_tags: list[str], all_tags: list[str], steps: list[str]) -> list[dict]:
    added = []
    seen: set[str] = set()

    for tag in top_tags:
        for query in _queries_for_tag(tag):
            raw = _serper_search(query)
            steps.append(f"🔍 Serper [{tag}] '{query}' → {len(raw)} 条")

            # Domain filter
            filtered = []
            for r in raw:
                d = _domain(r["url"])
                if d in BLOCKED_DOMAINS:
                    continue
                if r["url"] not in seen and not _already_seen(r["url"]):
                    r["_domain"] = d
                    filtered.append(r)

            blocked_count = len(raw) - len(filtered)
            if blocked_count:
                steps.append(f"   ↳ 屏蔽 {blocked_count} 条（黑名单域名）")

            if not filtered:
                steps.append("   ↳ 无新内容")
                continue

            scores = _score_items(filtered, all_tags, tag)

            for item, score in zip(filtered, scores):
                d = item["_domain"]
                threshold = MIN_SCORE_TRUSTED if d in TRUSTED_DOMAINS else MIN_SCORE_UNKNOWN
                seen.add(item["url"])
                if score >= threshold:
                    add_inbox_item(
                        title=item["title"], url=item["url"],
                        intent="read", description=item.get("description", ""),
                        note=f"AI 发现 · {tag}", source="discovery", priority="normal",
                    )
                    added.append({"title": item["title"], "url": item["url"],
                                  "description": item.get("description", ""),
                                  "tag": tag, "score": score, "domain": d})
                    tier = "✓" if d in TRUSTED_DOMAINS else "✓?"
                    steps.append(f"   {tier} ({score}分, {d}): {item['title'][:45]}")

    return added


# ── Source 2: Custom curated pages ────────────────────────────────────────────

def _fetch_custom_source(source: dict) -> list[dict]:
    """Scrape a curated link-list page, return extracted {title, url} items."""
    skip = source.get("skip_domains", set())
    try:
        resp = cffi_requests.get(source["url"], impersonate="chrome", timeout=15)
        resp.raise_for_status()
    except Exception as e:
        log.warning(f"[discovery] custom source failed {source['url']}: {e}")
        return []

    # Extract <a href="...">title</a> pairs
    links = re.findall(
        r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>\s*([^<]{8,120})',
        resp.text, re.IGNORECASE,
    )
    results, seen_urls = [], set()
    for url, title in links:
        if not url.startswith("http"):
            continue
        d = _domain(url)
        if d in skip or d in BLOCKED_DOMAINS:
            continue
        url_clean = url.split("?")[0]
        if url_clean in seen_urls:
            continue
        seen_urls.add(url_clean)
        results.append({"title": title.strip(), "url": url_clean, "description": ""})

    return results


def _run_custom_sources(steps: list[str]) -> list[dict]:
    added = []
    for source in CUSTOM_SOURCES:
        items = _fetch_custom_source(source)
        steps.append(f"📰 {source['name']}: 抓取到 {len(items)} 条链接")

        fresh = [i for i in items if not _already_seen(i["url"])]
        skipped = len(items) - len(fresh)
        if skipped:
            steps.append(f"   ↳ 跳过 {skipped} 条（已存在）")

        for item in fresh:
            add_inbox_item(
                title=item["title"], url=item["url"],
                intent="read", description="",
                note=f"来自 {source['name']}",
                source="discovery", priority="high",
            )
            added.append({"title": item["title"], "url": item["url"],
                          "tag": source["tag"], "score": 100,
                          "domain": _domain(item["url"])})
            steps.append(f"   ✓ {item['title'][:55]}")

    return added


# ── Main ──────────────────────────────────────────────────────────────────────

def run_discovery_sync() -> dict:
    steps: list[str] = []

    if not os.getenv("SERPER_API_KEY"):
        return {"ok": False, "reason": "SERPER_API_KEY 未配置", "added": 0, "items": [], "steps": ["❌ SERPER_API_KEY 未设置"]}

    tags = list_all_tags()
    if not tags:
        return {"ok": False, "reason": "知识库暂无标签", "added": 0, "items": [], "steps": ["❌ 知识库无标签"]}

    top_tags = [t["tag"] for t in tags[:5]]
    all_tags  = [t["tag"] for t in tags[:20]]
    steps.append(f"✓ 搜索主题：{top_tags}")

    serper_items = _run_serper(top_tags, all_tags, steps)
    custom_items = _run_custom_sources(steps)

    all_items = serper_items + custom_items
    steps.append(f"完成：Serper {len(serper_items)} 条 + 定制信源 {len(custom_items)} 条")

    return {
        "ok": True,
        "added": len(all_items),
        "tags_searched": top_tags,
        "items": all_items,
        "steps": steps,
    }


async def run_daily_discovery() -> dict:
    import asyncio
    return await asyncio.to_thread(run_discovery_sync)
