"""
真正的 Agent Loop — ReAct 模式
用 DeepSeek function calling 驱动，yield 结构化事件流供前端渲染。

事件类型：
  {"type": "thinking", "text": "..."}      — 工具调用前的状态文字
  {"type": "tool_start", "name": "...", "args": {...}}  — 工具开始
  {"type": "tool_end", "name": "...", "result": "..."}  — 工具结果
  {"type": "text", "chunk": "..."}          — 最终回答的流式文字
  {"type": "done"}                           — 结束
"""

import json
import logging
from openai import OpenAI
from dotenv import load_dotenv
import os
import re
from datetime import datetime

load_dotenv()

log = logging.getLogger("agent_loop")

# ── 工具定义 ────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "从大脑向量索引中语义检索相关内容，返回最相关的文章片段列表。用于回答问题、寻找联系、获取上下文。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索查询词或问题"},
                    "limit": {"type": "integer", "description": "返回结果数量，默认6", "default": 6}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_articles",
            "description": "按标题、文件名、摘要在文章库 SQLite 中确定性查找文章，返回 article_id、标题和路径。用户提到具体文章名时优先使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "文章标题、标题片段或文件名"},
                    "limit": {"type": "integer", "description": "返回数量，默认10", "default": 10}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_article_content",
            "description": "读取指定文章的完整 Markdown 内容。已知 article_id 或 find_articles 找到文章后使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "article_id": {"type": "string", "description": "文章 ID"},
                    "title": {"type": "string", "description": "如果不知道 ID，可提供标题让系统查找"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "synthesize",
            "description": "针对某个主题，跨所有文章进行综合分析，返回大脑对该主题的综合理解。适合生成洞察、写总结。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "要综合分析的主题或问题"},
                    "limit": {"type": "integer", "description": "参考文章数量，默认15", "default": 15}
                },
                "required": ["topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_insight",
            "description": "将一条洞察或综合分析结果写回大脑，持久化存储。用于将推理结果固化为知识。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "洞察标题"},
                    "body": {"type": "string", "description": "洞察正文（Markdown 格式）"},
                    "slug": {"type": "string", "description": "文件名标识，英文小写+连字符，如 ai-agents-2025"}
                },
                "required": ["title", "body", "slug"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_article",
            "description": "将全新的完整文章、全文翻译、长笔记或可作为文章阅读的内容写入知识库文章列表。只有用户明确要求新建文章时使用；如果是在当前文章中补全/覆盖中文部分，使用 update_article_content。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "文章标题"},
                    "content": {"type": "string", "description": "完整 Markdown 正文"},
                    "summary": {"type": "string", "description": "简短摘要，可选"},
                    "source_url": {"type": "string", "description": "来源 URL，可选"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "标签，可选"
                    }
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_article_content",
            "description": "更新已有文章的 Markdown 内容。适合把翻译覆盖到当前原文章的中文部分，而不是创建新文章。",
            "parameters": {
                "type": "object",
                "properties": {
                    "article_id": {"type": "string", "description": "文章 ID；省略时使用当前页面 articleId"},
                    "content": {"type": "string", "description": "要写入的 Markdown 正文"},
                    "mode": {
                        "type": "string",
                        "enum": ["replace_chinese_section", "replace_all", "append"],
                        "description": "replace_chinese_section 会保留原文英文部分，只覆盖开头中文部分"
                    },
                    "summary": {"type": "string", "description": "更新后的摘要，可选"}
                },
                "required": ["content", "mode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "translate_article_chinese_section",
            "description": "自动读取已有文章的英文原文部分，重新翻译成中文，并覆盖该文章的中文部分，保留英文原文不动。适合用户说“重翻译中文部分/覆盖原中文部分”。",
            "parameters": {
                "type": "object",
                "properties": {
                    "article_id": {"type": "string", "description": "文章 ID；省略时使用当前页面 articleId"},
                    "title": {"type": "string", "description": "如果不知道 ID，可提供文章标题让系统查找"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_recent_articles",
            "description": "列出最近添加的文章（标题、标签、摘要）。用于了解当前知识库状态。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "返回数量，默认10", "default": 10}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_brain_stats",
            "description": "获取大脑当前统计信息：文章数、标签分布、嵌入状态等。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "抓取一个网页的文字内容，用于主动获取外部知识、验证新概念、补充大脑中没有的背景信息。遇到不熟悉的概念或需要最新信息时优先使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要抓取的网页 URL，必须是完整 URL（含 https://）"},
                    "max_chars": {"type": "integer", "description": "最大返回字符数，默认3000", "default": 3000}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "propose_js",
            "description": "创建一个需要用户确认后才会在浏览器中执行的 JavaScript 提案。用于修改当前页面、调用页面 API、组合多个页面操作。不要直接声称已经执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "提案标题"},
                    "summary": {"type": "string", "description": "这段 JS 将做什么"},
                    "code": {"type": "string", "description": "只使用 api 和 ctx 的异步 JS 代码，例如 await api.request('PATCH', `/api/articles/${ctx.articleId}`, {title:'新标题'});"},
                    "risk_level": {"type": "string", "enum": ["low", "medium", "high"], "description": "风险等级"},
                    "expected_effects": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "预计影响，逐条列出"
                    }
                },
                "required": ["title", "summary", "code"]
            }
        }
    },
]

TOOL_THINKING = {
    "recall": lambda args: f"检索大脑：{args.get('query', '')}",
    "find_articles": lambda args: f"查找文章：{args.get('query', '')}",
    "get_article_content": lambda args: "读取文章全文",
    "synthesize": lambda args: f"综合分析：{args.get('topic', '')}",
    "write_insight": lambda args: f"写入洞察：{args.get('title', '')}",
    "save_article": lambda args: f"保存文章：{args.get('title', '')}",
    "update_article_content": lambda args: "更新文章内容",
    "translate_article_chinese_section": lambda args: "重翻译并覆盖中文部分",
    "list_recent_articles": lambda args: "查看最近文章…",
    "get_brain_stats": lambda args: "读取大脑统计…",
    "fetch_url": lambda args: f"抓取网页：{args.get('url', '')}",
    "propose_js": lambda args: f"创建操作提案：{args.get('title', '')}",
}

# ── 工具执行 ─────────────────────────────────────────────────────────────────

def _execute_tool(name: str, args: dict, page_context: dict | None = None) -> str:
    from services import memory, db

    if name == "recall":
        results = memory.recall(args["query"], args.get("limit", 6))
        if not results:
            matches = _find_articles(args["query"], args.get("limit", 6), db)
            if not matches:
                return "未找到相关内容。"
            return _format_article_matches(matches, include_hint=True)
        lines = []
        for r in results:
            title = r.get("title") or r.get("file", "")
            snippet = (r.get("snippet") or r.get("content") or "")[:200]
            lines.append(f"**{title}**\n{snippet}")
        return "\n\n---\n\n".join(lines)

    elif name == "find_articles":
        matches = _find_articles(args["query"], args.get("limit", 10), db)
        return _format_article_matches(matches) if matches else "没有在文章库中找到匹配文章。"

    elif name == "get_article_content":
        article = None
        if args.get("article_id"):
            article = db.get_article(args["article_id"])
        elif args.get("title"):
            matches = _find_articles(args["title"], 1, db)
            article = matches[0] if matches else None
        if not article:
            return "读取失败：没有找到这篇文章。"
        content = _read_article_markdown(article)
        if not content:
            return f"读取失败：文章《{article.get('title', '')}》没有可读取的 Markdown 文件。"
        return json.dumps(
            {
                "article_id": article["id"],
                "title": article["title"],
                "path": article.get("article_md_path"),
                "content": content,
            },
            ensure_ascii=False,
        )

    elif name == "synthesize":
        result = memory.synthesize(args["topic"], args.get("limit", 15))
        return result or "大脑暂无关于该主题的足够内容。"

    elif name == "write_insight":
        ok = memory.write_page(args["slug"], args["title"], args["body"], subdir="insights")
        return "洞察已写入大脑。" if ok else "写入失败，请检查 gbrain 服务。"

    elif name == "save_article":
        title = (args.get("title") or "未命名文章").strip()
        content = (args.get("content") or "").strip()
        if len(content) < 80:
            return "保存失败：正文太短，不适合作为文章写入知识库。"

        scripts_dir = "static/scripts"
        os.makedirs(scripts_dir, exist_ok=True)
        safe_title = re.sub(r'[^\w\u4e00-\u9fff]+', '_', title).strip('_')[:50] or "agent_article"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_title}_{ts}.md"
        path = os.path.join(scripts_dir, filename)
        if not content.startswith("# "):
            content = f"# {title}\n\n{content}"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        summary = (args.get("summary") or content[:300]).replace("\n", " ")[:300]
        article_id = db.add_article(
            title=title,
            source_url=args.get("source_url") or "",
            source_type="agent",
            summary=summary,
            article_md_path=f"/{path}",
            word_count=len(content),
        )
        tags = args.get("tags") or []
        if isinstance(tags, list) and tags:
            db.update_tags(article_id, [str(t) for t in tags[:8]])

        article = db.get_article(article_id)
        indexed = False
        if article:
            indexed = memory.remember(article)
        db.add_evolution_log(
            "article_saved",
            f"Agent 将《{title}》写入文章知识库。" + ("" if indexed else " GBrain 索引稍后可重试。"),
            after={"article_id": article_id, "path": f"/{path}", "indexed": indexed},
            artifact_type="article",
            artifact_id=article_id,
        )
        return json.dumps(
            {
                "ok": True,
                "article_id": article_id,
                "title": title,
                "url": f"/article/{article_id}",
                "path": f"/{path}",
                "indexed": indexed,
            },
            ensure_ascii=False,
        )

    elif name == "update_article_content":
        article_id = args.get("article_id") or (page_context or {}).get("articleId")
        if not article_id:
            return "更新失败：缺少 article_id，且当前页面上下文没有 articleId。"
        article = db.get_article(article_id)
        if not article or not article.get("article_md_path"):
            return "更新失败：文章不存在或没有 Markdown 文件。"

        file_path = article["article_md_path"].lstrip("/")
        content = (args.get("content") or "").strip()
        mode = args.get("mode") or "replace_chinese_section"
        if len(content) < 80:
            return "更新失败：正文太短。"
        if not os.path.exists(file_path):
            return f"更新失败：找不到文件 {file_path}。"

        with open(file_path, "r", encoding="utf-8") as f:
            old = f.read()

        if mode == "replace_all":
            new_content = content
        elif mode == "append":
            new_content = old.rstrip() + "\n\n" + content + "\n"
        else:
            new_content = _replace_chinese_section(old, content)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        summary = (args.get("summary") or content[:300]).replace("\n", " ")[:300]
        db.update_article_summary(article_id, summary, len(new_content))
        refreshed = db.get_article(article_id)
        indexed = memory.remember(refreshed) if refreshed else False
        db.add_evolution_log(
            "article_updated",
            f"Agent 更新了《{article['title']}》的文章内容。",
            before={"path": file_path, "chars": len(old)},
            after={"path": file_path, "chars": len(new_content), "mode": mode, "indexed": indexed},
            artifact_type="article",
            artifact_id=article_id,
        )
        return json.dumps(
            {
                "ok": True,
                "article_id": article_id,
                "title": article["title"],
                "url": f"/article/{article_id}",
                "path": file_path,
                "mode": mode,
                "indexed": indexed,
            },
            ensure_ascii=False,
        )

    elif name == "translate_article_chinese_section":
        article = None
        article_id = args.get("article_id") or (page_context or {}).get("articleId")
        if article_id:
            article = db.get_article(article_id)
        elif args.get("title"):
            matches = _find_articles(args["title"], 1, db)
            article = matches[0] if matches else None
        if not article or not article.get("article_md_path"):
            return "翻译失败：没有找到可更新的文章。"

        file_path = article["article_md_path"].lstrip("/")
        if not os.path.exists(file_path):
            return f"翻译失败：找不到文件 {file_path}。"
        with open(file_path, "r", encoding="utf-8") as f:
            old = f.read()

        english = _extract_english_section(old)
        if len(english) < 200:
            return "翻译失败：没有识别到足够长的英文原文部分。"

        from services.llm import translate_full_article

        translated, tags = translate_full_article(english)
        translated = (translated or "").strip()
        if len(translated) < 200:
            return "翻译失败：模型返回的中文译文过短。"

        zh_markdown = f"# {article['title']}\n\n{translated}"
        new_content = _replace_chinese_section(old, zh_markdown)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        summary = " ".join(translated.split())[:300]
        db.update_article_summary(article["id"], summary, len(new_content))
        if tags:
            db.update_tags(article["id"], tags)
        refreshed = db.get_article(article["id"])
        indexed = memory.remember(refreshed) if refreshed else False
        db.add_evolution_log(
            "article_translated",
            f"Agent 重新翻译并覆盖《{article['title']}》的中文部分。",
            before={"path": file_path, "english_chars": len(english)},
            after={"path": file_path, "translated_chars": len(translated), "indexed": indexed},
            artifact_type="article",
            artifact_id=article["id"],
        )
        return json.dumps(
            {
                "ok": True,
                "article_id": article["id"],
                "title": article["title"],
                "url": f"/article/{article['id']}",
                "path": file_path,
                "translated_chars": len(translated),
                "indexed": indexed,
            },
            ensure_ascii=False,
        )

    elif name == "list_recent_articles":
        articles = db.list_articles(limit=args.get("limit", 10))
        if not articles:
            return "知识库为空。"
        lines = []
        for a in articles:
            tags = json.loads(a.get("tags") or "[]") if isinstance(a.get("tags"), str) else (a.get("tags") or [])
            tag_str = ", ".join(tags[:4]) if tags else "无标签"
            summary = (a.get("summary") or "")[:80]
            lines.append(f"- 《{a['title']}》[{tag_str}] {summary}")
        return "\n".join(lines)

    elif name == "get_brain_stats":
        stats = memory.stats()
        return json.dumps(stats, ensure_ascii=False, indent=2) if stats else "无法获取统计信息。"

    elif name == "fetch_url":
        url = args.get("url", "").strip()
        if not url or not url.startswith("http"):
            return "无效 URL，请提供完整的 https:// 开头的地址。"
        max_chars = args.get("max_chars", 3000)
        try:
            from services.extractor import extract_content
            content, title, _ = extract_content(url)
            if not content:
                return f"无法提取页面内容：{url}"
            header = f"**{title}**\n来源：{url}\n\n" if title else f"来源：{url}\n\n"
            return header + content[:max_chars]
        except Exception as e:
            return f"抓取失败：{e}"

    elif name == "propose_js":
        from services.agent_proposals import create_js_proposal

        proposal = create_js_proposal(
            title=args.get("title", "JS 操作提案"),
            summary=args.get("summary", ""),
            code=args.get("code", ""),
            page_context=page_context or {},
            risk_level=args.get("risk_level", "medium"),
            expected_effects=args.get("expected_effects") or [],
        )
        return json.dumps(
            {
                "proposal_id": proposal["id"],
                "title": proposal["title"],
                "summary": proposal["summary"],
                "risk_level": proposal["risk_level"],
                "expected_effects": proposal.get("expected_effects", []),
                "status": proposal["status"],
            },
            ensure_ascii=False,
        )

    return f"未知工具：{name}"


# ── Agent Loop ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是用户的第二大脑助手。你可以调用工具检索、综合、写入用户的个人知识库，也可以主动抓取外部网页补充知识。

行为准则：
- 先思考需要哪些信息，再调用工具。
- 不要假设，用 recall 或 list_recent_articles 获取真实数据。
- 当用户提到某一篇具体文章标题时，先用 find_articles 找到 article_id，再用 get_article_content 读取全文；不要只依赖 recall。
- 遇到大脑中没有的概念或需要最新信息时，主动用 fetch_url 抓取外部资料。
- 综合分析后，如果产生了有价值的洞察，主动用 write_insight 写回大脑。
- 当用户要求重新翻译当前文章/原文章的中文部分，并且文章后半部分已有英文原文时，必须使用 translate_article_chinese_section；不要自己把译文塞进 update_article_content。
- 当用户已经提供了完整中文正文，要求写入“当前文章”或“原文章”的中文部分时，使用 update_article_content，mode 用 replace_chinese_section；不要新建文章。
- 只有用户明确要求新建文章/另存为新文章时，才使用 save_article。
- write_insight 只用于短洞察、综合结论、连接发现，不用于保存完整文章。
- 当用户要求你修改页面、修改文章数据、跳转页面、组合页面 API 操作时，使用 propose_js 创建提案；不要声称已经执行。
- propose_js 的代码必须只使用 api 和 ctx，不要使用 window、document、localStorage、fetch 或 eval。
- 如果当前页面上下文里有 allowedApiRoutes，优先使用其中列出的 API。
- 回答简洁、有见地，避免废话。
- 用中文回答。"""


def run_stream(
    user_message: str,
    history: list[dict] | None = None,
    max_steps: int = 8,
    page_context: dict | None = None,
):
    """
    运行 Agent Loop，yield 结构化事件（dict）。
    调用方将事件序列化为 NDJSON 行发送给前端。
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        yield {"type": "text", "chunk": "错误：未配置 DEEPSEEK_API_KEY。"}
        yield {"type": "done"}
        return

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if page_context:
        messages.append({
            "role": "system",
            "content": "当前浏览器页面上下文：\n" + json.dumps(page_context, ensure_ascii=False, indent=2),
        })
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    for step in range(max_steps):
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=2000,
            temperature=0.6,
            stream=False,
        )

        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        # 最终回答 — 流式输出文字
        if finish_reason == "stop" or not msg.tool_calls:
            final_text = msg.content or ""
            # 按句子/段落 chunk 输出，模拟流式
            for chunk in _chunk_text(final_text):
                yield {"type": "text", "chunk": chunk}
            yield {"type": "done"}
            return

        # 工具调用
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                }
                for tc in msg.tool_calls
            ]
        })

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {}

            thinking_text = TOOL_THINKING.get(tool_name, lambda a: tool_name)(args)
            yield {"type": "thinking", "text": thinking_text}
            yield {"type": "tool_start", "name": tool_name, "args": args}

            log.info(f"[agent] tool={tool_name} args={args}")
            result = _execute_tool(tool_name, args, page_context=page_context)
            log.info(f"[agent] tool={tool_name} result_len={len(result)}")

            yield {"type": "tool_end", "name": tool_name, "result": result[:600]}

            if tool_name == "propose_js":
                try:
                    proposal_ref = json.loads(result)
                    from services import db
                    proposal = db.get_agent_proposal(proposal_ref["proposal_id"])
                    if proposal:
                        yield {"type": "js_proposal", "proposal": proposal}
                except Exception as e:
                    log.warning("[agent] failed to emit js proposal: %s", e)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    # 超出步数限制
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages + [{"role": "user", "content": "请根据以上信息给出最终回答。"}],
        max_tokens=1500,
        temperature=0.6,
        stream=False,
    )
    final_text = response.choices[0].message.content or ""
    for chunk in _chunk_text(final_text):
        yield {"type": "text", "chunk": chunk}
    yield {"type": "done"}


def _chunk_text(text: str, size: int = 80):
    """把文本按 size 字符分块，模拟流式输出。"""
    for i in range(0, len(text), size):
        yield text[i:i + size]


def _replace_chinese_section(old: str, zh_markdown: str) -> str:
    """Replace the translated Chinese block while preserving title/header and English source."""
    separators = list(re.finditer(r"(?m)^---\s*$", old))
    if len(separators) >= 2:
        first = separators[0]
        second = separators[1]
        prefix = old[:first.end()].rstrip()
        suffix = old[second.start():].lstrip()
        return f"{prefix}\n\n{zh_markdown.strip()}\n\n{suffix}"
    if len(separators) == 1:
        first = separators[0]
        prefix = old[:first.end()].rstrip()
        return f"{prefix}\n\n{zh_markdown.strip()}\n"
    return zh_markdown.strip() + "\n"


def _extract_english_section(markdown: str) -> str:
    """Extract the preserved English source after the second section separator."""
    separators = list(re.finditer(r"(?m)^---\s*$", markdown))
    if len(separators) >= 2:
        text = markdown[separators[1].end():].strip()
    elif separators:
        text = markdown[separators[0].end():].strip()
    else:
        text = markdown
    text = re.sub(r"(?m)^\|\s*\|$", "", text).strip()
    return text


def _normalize_lookup(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("’", "'").replace("‘", "'").replace("`", "'")
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", text)


def _find_articles(query: str, limit: int, db_module) -> list[dict]:
    needle = _normalize_lookup(query)
    if not needle:
        return []
    candidates = db_module.list_articles(limit=500)
    scored = []
    for article in candidates:
        fields = [
            article.get("title") or "",
            article.get("summary") or "",
            article.get("article_md_path") or "",
            article.get("source_url") or "",
        ]
        normalized_fields = [_normalize_lookup(f) for f in fields]
        score = 0
        if normalized_fields and normalized_fields[0] == needle:
            score = 100
        elif normalized_fields and needle in normalized_fields[0]:
            score = 80
        elif any(needle in f for f in normalized_fields[2:]):
            score = 65
        elif any(needle in f for f in normalized_fields):
            score = 45
        if score:
            item = dict(article)
            item["_score"] = score
            scored.append(item)
    scored.sort(key=lambda a: (-a["_score"], a.get("created_at") or ""))
    return scored[:limit]


def _format_article_matches(matches: list[dict], include_hint: bool = False) -> str:
    lines = []
    if include_hint:
        lines.append("GBrain 没有返回结果，但 SQLite 文章库找到了这些匹配：")
    for article in matches:
        summary = (article.get("summary") or "").replace("\n", " ")[:160]
        lines.append(
            f"- id: {article['id']}\n"
            f"  title: {article.get('title', '')}\n"
            f"  path: {article.get('article_md_path') or ''}\n"
            f"  summary: {summary}"
        )
    if include_hint:
        lines.append("如需完整内容，请继续调用 get_article_content。")
    return "\n".join(lines)


def _read_article_markdown(article: dict, max_chars: int = 24000) -> str:
    path = (article.get("article_md_path") or "").lstrip("/")
    if not path or not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()[:max_chars]


# 保留旧接口兼容 agent.py 的定时任务调用
def run(user_message: str, history=None, max_steps: int = 8, stream: bool = False, page_context=None):
    accumulated = []
    for event in run_stream(user_message, history=history, max_steps=max_steps, page_context=page_context):
        if event["type"] == "text":
            accumulated.append(event["chunk"])
    return "".join(accumulated)


def on_article_added(article: dict):
    """
    新文章入库后自动触发。在后台线程中运行。
    Agent 会：
    1. 分析文章内容
    2. 用 recall 找已有知识中的关联
    3. 生成洞察写回大脑
    4. 将核心洞察更新到文章的 insights 字段
    """
    from services import db

    article_id = article.get("id", "")
    title = article.get("title", "未知标题")
    summary = (article.get("summary") or "")[:500]
    tags = article.get("tags") or "[]"

    if not summary:
        log.info(f"[agent] skip on_article_added for '{title}' — no summary")
        return

    prompt = f"""刚刚入库了一篇新文章：《{title}》
标签：{tags}
摘要：{summary}

请完成以下任务：
1. 用 recall 在大脑中搜索与这篇文章相关的已有知识（至少搜索2个不同角度）
2. 找出这篇文章与已有知识之间最有价值的联系或对比
3. 提炼出1-2条真正有洞察力的结论，用 write_insight 写回大脑（slug 用 insight-{article_id[:8]}）
4. 最后用一句话总结：这篇文章为大脑补充了什么新视角

不要复述文章内容，专注于跨文章的联系和新发现。"""

    log.info(f"[agent] analyzing new article: '{title}'")
    try:
        result = run(prompt, max_steps=10)
        log.info(f"[agent] article analysis done: '{title}' — {result[:80]}")

        # 把 agent 分析结果存回 insights 字段（补充而非覆盖）
        existing = article.get("insights")
        if existing:
            try:
                import json as _json
                ins = _json.loads(existing) if isinstance(existing, str) else existing
            except Exception:
                ins = {}
        else:
            ins = {}

        ins["agent_analysis"] = result[:800]
        db.update_insights(article_id, ins)
        log.info(f"[agent] insights updated for '{title}'")
    except Exception as e:
        log.error(f"[agent] on_article_added error for '{title}': {e}")
