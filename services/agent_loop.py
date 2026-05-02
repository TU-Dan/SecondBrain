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
]

TOOL_THINKING = {
    "recall": lambda args: f"检索大脑：{args.get('query', '')}",
    "synthesize": lambda args: f"综合分析：{args.get('topic', '')}",
    "write_insight": lambda args: f"写入洞察：{args.get('title', '')}",
    "list_recent_articles": lambda args: "查看最近文章…",
    "get_brain_stats": lambda args: "读取大脑统计…",
}

# ── 工具执行 ─────────────────────────────────────────────────────────────────

def _execute_tool(name: str, args: dict) -> str:
    from services import memory, db

    if name == "recall":
        results = memory.recall(args["query"], args.get("limit", 6))
        if not results:
            return "未找到相关内容。"
        lines = []
        for r in results:
            title = r.get("title") or r.get("file", "")
            snippet = (r.get("snippet") or r.get("content") or "")[:200]
            lines.append(f"**{title}**\n{snippet}")
        return "\n\n---\n\n".join(lines)

    elif name == "synthesize":
        result = memory.synthesize(args["topic"], args.get("limit", 15))
        return result or "大脑暂无关于该主题的足够内容。"

    elif name == "write_insight":
        ok = memory.write_page(args["slug"], args["title"], args["body"], subdir="insights")
        return "洞察已写入大脑。" if ok else "写入失败，请检查 gbrain 服务。"

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

    return f"未知工具：{name}"


# ── Agent Loop ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是用户的第二大脑助手。你可以调用工具检索、综合、写入用户的个人知识库。

行为准则：
- 先思考需要哪些信息，再调用工具。
- 不要假设，用 recall 或 list_recent_articles 获取真实数据。
- 综合分析后，如果产生了有价值的洞察，主动用 write_insight 写回大脑。
- 回答简洁、有见地，避免废话。
- 用中文回答。"""


def run_stream(user_message: str, history: list[dict] | None = None, max_steps: int = 8):
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
            result = _execute_tool(tool_name, args)
            log.info(f"[agent] tool={tool_name} result_len={len(result)}")

            yield {"type": "tool_end", "name": tool_name, "result": result[:600]}

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


# 保留旧接口兼容 agent.py 的定时任务调用
def run(user_message: str, history=None, max_steps: int = 8, stream: bool = False):
    accumulated = []
    for event in run_stream(user_message, history=history, max_steps=max_steps):
        if event["type"] == "text":
            accumulated.append(event["chunk"])
    return "".join(accumulated)
