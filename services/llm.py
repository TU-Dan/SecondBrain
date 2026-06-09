import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

CHUNK_THRESHOLD = 12000


def _get_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("Error: DEEPSEEK_API_KEY not found in environment variables.")
        return None
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def detect_language(text: str) -> str:
    """Returns 'zh' if mostly Chinese, else 'en'."""
    sample = text[:3000]
    if not sample:
        return 'en'
    chinese_chars = sum(1 for c in sample if '\u4e00' <= c <= '\u9fff')
    return 'zh' if chinese_chars / len(sample) > 0.1 else 'en'


def chunk_text(text: str, chunk_size: int = CHUNK_THRESHOLD) -> list[str]:
    """Split text into chunks at sentence boundaries."""
    sentence_endings = {'。', '！', '？', '!', '?', '\n'}
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunks.append(text[start:])
            break

        boundary = end
        for i in range(end, min(end + 200, len(text))):
            if text[i] in sentence_endings:
                boundary = i + 1
                break

        chunks.append(text[start:boundary])
        start = boundary

    return [c for c in chunks if c.strip()]


_META_PATTERNS = [
    r'^好的[，,].*\n?',
    r'^收到[，,。].*\n?',
    r'^作为.{0,20}编辑.*\n?',
    r'^我[将会]为你.*\n?',
    r'^我[将会]帮你.*\n?',
    r'^以下是.*播客.*\n?',
    r'^下面是.*播客.*\n?',
    r'^接下来[，,]我[将会].*\n?',
]

def _strip_meta(text: str) -> str:
    """Remove LLM self-introduction lines from the start of output."""
    import re
    for pattern in _META_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.MULTILINE)
    return text.lstrip()


def polish_chunk(chunk: str, part_index: int, total_parts: int) -> str | None:
    """Polish a text chunk for podcast. Preserves all content. Returns Markdown."""
    client = _get_client()
    if not client:
        return None

    prompt = f"""你正在处理一篇长内容的第 {part_index + 1}/{total_parts} 部分。

任务：
把原文整理成适合中文播客朗读的 Markdown 讲稿。

硬性要求：
1. 全部使用中文；英文内容要翻译，中文内容要润色。
2. 保留原文所有观点、细节、数据、例子和推理顺序，不压缩、不跳段、不擅自总结。
3. 去掉字幕噪音：重复句、口癖、无意义填充词、残缺时间戳。
4. 语言自然、口语化，像真实主播在讲，但不要添加原文没有的新观点。
5. 用 Markdown 组织：必要时使用二级标题，重点可加粗。
6. 只输出正文，不要确认语、角色介绍、任务说明或“以下是”。

原文：
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是严谨的中文播客文案编辑。你的优先级是信息完整、顺序保真、朗读自然。只输出正文。"},
                {"role": "user", "content": prompt + chunk}
            ],
            max_tokens=8000,
            temperature=0.7
        )
        result = _strip_meta(response.choices[0].message.content)
        # Prepend transition phrase for non-first parts
        if part_index > 0:
            result = f"接下来，{result}"
        return result
    except Exception as e:
        print(f"DeepSeek API Error (part {part_index + 1}): {e}")
        return None


def _parse_tags(raw: str) -> tuple[str, list[str]]:
    """Split LLM output into (script, tags). Tags follow a '---TAGS---' marker."""
    marker = "---TAGS---"
    idx = raw.rfind(marker)
    if idx == -1:
        return raw.strip(), []
    script = raw[:idx].strip()
    tag_line = raw[idx + len(marker):].strip()
    # Accept comma or Chinese comma separated, strip whitespace and #
    tags = [t.strip().lstrip("#").strip() for t in re.split(r'[,，]', tag_line) if t.strip()]
    return script, tags[:8]  # cap at 8 tags


def literal_translate(text: str) -> tuple[str, list[str]] | None:
    """English (or non-Chinese primary) → Chinese literal translation only.
    No summarization, no omission. Returns (script_markdown, tags) or None."""
    client = _get_client()
    if not client:
        return None

    prompt = """任务：将以下全文逐句直译为中文。

翻译原则：
1. 只翻译，不摘要、不改写、不提炼、不删减。
2. 保持原文段落顺序、论证顺序和信息密度。
3. 专有名词优先使用通行译名；没有通行译名时保留英文。
4. 代码、URL、公式、数字、引用来源可保留原样。
5. 中文要通顺，但不要二次创作成鸡汤、演讲稿或播客口吻。
6. 使用 Markdown 分段，必要时保留或翻译小标题。
7. 只输出译文正文，不要确认语、角色介绍或“以下是”。
8. 正文末尾另起一行输出标签，格式固定为：
---TAGS---
标签1, 标签2, 标签3

原文：
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "你是专业直译译者。优先保真，其次通顺。只输出中文译文和末尾标签行。",
                },
                {"role": "user", "content": prompt + text},
            ],
            max_tokens=8000,
            temperature=0.3,
        )
        raw = _strip_meta(response.choices[0].message.content)
        return _parse_tags(raw)
    except Exception as e:
        print(f"DeepSeek API Error (literal_translate): {e}")
        return None


def literal_translate_chunk(chunk: str, part_index: int, total_parts: int) -> str | None:
    """Long text: translate one chunk literally. No tags in chunk output."""
    client = _get_client()
    if not client:
        return None

    prompt = f"""你正在翻译长文的第 {part_index + 1}/{total_parts} 部分。

任务：逐句直译为中文。

硬性要求：
1. 只翻译，不摘要、不合并段落、不删减。
2. 保持本段内部顺序、信息密度和论证关系。
3. 全部使用中文；代码、URL、公式、数字可保留原样。
4. 使用 Markdown 分段。
5. 只输出译文，不要确认语、角色介绍或“以下是”。

原文：
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "你是专业直译译者。只输出本段中文译文，不输出任何其他说明。",
                },
                {"role": "user", "content": prompt + chunk},
            ],
            max_tokens=8000,
            temperature=0.3,
        )
        result = _strip_meta(response.choices[0].message.content)
        if part_index > 0:
            result = f"接下来，{result}"
        return result
    except Exception as e:
        print(f"DeepSeek API Error (literal chunk {part_index + 1}): {e}")
        return None


def distill_and_translate(text: str) -> tuple[str, list[str]] | None:
    """Create a concise Chinese podcast script.

    This is intentionally a summary mode. The default podcast generation path
    uses format_transcript()/polish_chunk() to preserve source fidelity.
    Returns (script_markdown, tags) or None on failure."""
    client = _get_client()
    if not client:
        return None

    prompt = """任务：把以下原始文本蒸馏成一篇中文播客讲稿。

写作目标：
- 不是逐字翻译，而是保留原文最重要的观点、故事、案例、判断和细节。
- 去掉冗余口水和重复表达，让内容更适合听。
- 最终长度约 2000-5000 字，按原文信息量调整；不要为了凑字数空泛扩写。

结构要求：
1. 开头用 3-5 句交代这段内容最值得听的核心问题。
2. 正文按主题分段，使用 Markdown 二级标题。
3. 每个段落都要有明确观点和具体素材，避免“正确的废话”。
4. 结尾提炼一个能带走的认知或行动提醒。

语言要求：
1. 全部中文，口语化、自然、适合朗读。
2. 保留关键数据、人物、案例和原文中的锋利判断。
3. 不要确认语、角色介绍、任务说明或“以下是”。
4. 不要编造原文没有的信息。
5. 正文末尾另起一行输出标签，格式固定为：
---TAGS---
标签1, 标签2, 标签3

原文：
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是中文播客主笔。你擅长把复杂素材蒸馏成有观点、有细节、适合朗读的讲稿。只输出正文和末尾标签行。"},
                {"role": "user", "content": prompt + text}
            ],
            max_tokens=8000,
            temperature=0.7
        )
        raw = _strip_meta(response.choices[0].message.content)
        return _parse_tags(raw)
    except Exception as e:
        print(f"DeepSeek API Error: {e}")
        return None


def format_transcript(text: str) -> tuple[str, list[str]] | None:
    """Structure raw transcript into clean markdown without losing any content.
    Returns (markdown, tags) or None on failure."""
    client = _get_client()
    if not client:
        return None

    prompt = """任务：把以下原始文字稿整理成结构清晰的中文 Markdown 文档。

整理原则：
1. 信息完整优先：不删减、不压缩任何观点、细节、数据、案例。
2. 如果原文是英文，翻译为中文；如果已经是中文，只做清理和结构化。
3. 清除字幕噪音：重复句、时间戳残留、无意义填充词、断裂口癖。
4. 按主题使用二级标题（##）分段，关键术语可加粗。
5. 保持原始观点，不新增评论、不改写立场。
6. 只输出正文，不要确认语、角色介绍或“以下是”。
7. 正文末尾另起一行输出标签，格式固定为：
---TAGS---
标签1, 标签2, 标签3

原文：
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是严谨的文字整理编辑。你的优先级是完整、清晰、可存档。只输出正文和末尾标签行。"},
                {"role": "user", "content": prompt + text},
            ],
            max_tokens=8000,
            temperature=0.3,
        )
        raw = _strip_meta(response.choices[0].message.content)
        return _parse_tags(raw)
    except Exception as e:
        print(f"DeepSeek API Error (format_transcript): {e}")
        return None


def generate_title(text: str) -> str:
    """Generate a concise Chinese title from content. Falls back gracefully."""
    # Try first # heading in text
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()[:40]

    client = _get_client()
    if not client:
        return "未命名播客"
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是中文内容标题编辑。只输出一个标题，不加引号、序号、冒号副标题或任何前缀。"},
                {"role": "user", "content": (
                    "根据以下内容生成一个中文标题。\n"
                    "要求：\n"
                    "1. 不超过20个字。\n"
                    "2. 像真人取的标题，有具体对象或动作，不要空泛。\n"
                    "3. 不使用“揭秘”“震惊”“你必须知道”等廉价词。\n"
                    "4. 不使用“主标题：副标题”格式。\n\n"
                    f"内容：\n{text[:1500]}"
                )},
            ],
            max_tokens=40,
            temperature=0.5,
        )
        return response.choices[0].message.content.strip().strip('"').strip("'")[:40]
    except Exception as e:
        print(f"Title generation error: {e}")
        return "未命名播客"


def generate_daily_brief(articles: list[dict]) -> str | None:
    """Generate a daily review from a list of articles (title + summary).
    Returns a markdown string or None.
    """
    client = _get_client()
    if not client:
        return None

    items = "\n".join(
        f"{i+1}. 《{a['title']}》\n   {a.get('summary','')[:150]}"
        for i, a in enumerate(articles)
    )

    prompt = f"""以下是从知识库中抽取的 {len(articles)} 篇文章。请写一段“今日知识回顾”。

目标读者：
想改善生活、发展一人事业、提升判断力、理解世界变化的人。

输出要求：
1. 300-500字。
2. 不要逐篇流水账，要先找到这些文章之间的隐含主题或张力。
3. 每篇文章至少提炼一个核心观点，但要自然嵌入，不要列清单。
4. 结尾用一句“今日思考”收束：这些知识放在一起，对读者的生活/工作/判断意味着什么。
5. 语气像一个思维活跃的朋友在复盘，有温度但不鸡汤。
6. 直接输出正文，不要标题，不要“今日回顾”等前缀。

文章列表：
{items}
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是知识策展人。你擅长把分散文章串成一个有洞察的每日复盘。只输出正文。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
            temperature=0.8,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"DeepSeek API Error (generate_daily_brief): {e}")
        return None


def extract_insights(text: str) -> dict | None:
    """Extract structured insights from article text.
    Returns {"core": str, "insights": [str, str, str], "counterintuitive": str} or None.
    """
    client = _get_client()
    if not client:
        return None

    prompt = """任务：从以下文章中提取结构化洞见。

提取原则：
1. 不要做泛泛摘要，要抓住文章真正的核心判断。
2. 洞见要具体、可复述、能帮助用户重新理解一个问题。
3. 不要编造原文没有的信息。
4. 严格输出合法 JSON，不要 Markdown，不要解释。

JSON 格式：

{
  "core": "一句话概括文章最核心的论点（20-40字）",
  "insights": [
    "关键洞见1（15-30字）",
    "关键洞见2（15-30字）",
    "关键洞见3（15-30字）"
  ],
  "counterintuitive": "文章中最反直觉或最令人意外的一个发现（20-40字）"
}

文章内容：
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是内容分析专家。你只输出合法 JSON，不输出任何其他内容。"},
                {"role": "user", "content": prompt + text[:6000]},
            ],
            max_tokens=400,
            temperature=0.3,
        )
        import json
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        return json.loads(raw)
    except Exception as e:
        print(f"DeepSeek API Error (extract_insights): {e}")
        return None


def _build_social_post_prompt(text: str, format_type: str, pain_point: str = "") -> tuple[str, int, str]:
    pain_point_line = f"聚焦的痛点/角度：{pain_point}\n" if pain_point.strip() else ""

    if format_type == "insight":
        prompt = f"""请从以下文章中提炼一句适合做社媒短句/卡片标题的洞见。
{pain_point_line}要求：
1. 只输出一句话，20-60字。
2. 必须有清晰判断，最好带一点反常识、冲突感或认知翻转。
3. 不要摘要句，不要“本文认为”，不要正确但无用的废话。
4. 不要编造原文没有的概念。

文章内容：
{text[:3000]}"""
        max_tokens = 100
        system_prompt = "你是中文社媒内容主笔。你擅长把长文提炼成有观点、有细节、有传播力的内容。只输出正文。"

    elif format_type == "list":
        prompt = f"""请基于以下文章，写一篇适合公众号/小红书的清单体短内容。
{pain_point_line}目标：
- 从原文中提炼 3 个不同角度的关键洞见。
- 每条都要有“核心判断 + 具体解释 + 对读者有什么用”。

要求：
1. 标题要像真人写的，有好奇心或反常识，不要使用“主标题：副标题”。
2. 每条洞见用一句短标题开头，再用 2-3 句展开。
3. 总长 350-600 字。
4. 语言口语化，有画面感，避免空话、套话和 AI 总结腔。
5. 不要编造原文没有的信息。
6. 直接输出正文，不要说明或前缀。

文章内容：
{text[:5000]}"""
        max_tokens = 1000
        system_prompt = "你是中文社媒内容主笔。你擅长把长文提炼成有观点、有细节、有传播力的内容。只输出正文。"

    else:  # wechat
        prompt = f"""你是一位资深内容编辑。请基于以下文章，重构成一篇适合公众号发布的短文。
{pain_point_line}第一步：改稿诊断
阅读全文后，先判断这些问题，并在最终的【改稿诊断】里简洁说明：
- 这篇文章的核心主张是什么？用一句话说清楚。
- 文章当前最适合的主调是什么：认知分析 / 情绪共鸣 / 行动引导 / 故事叙述？
- 主调是否统一？是否存在两种声音打架？
- 最重要的转折、论点或最强素材在哪里？它是否被充分展开？
- 结尾应该开放、落地还是行动？原文是否软着陆？

第二步：确定改稿方向
必须做出明确选择，不要模糊：

主调选择（选一个，其余服从它）：
- 认知分析型：以洞察和逻辑为主干，例子服务于论点。
- 情绪共鸣型：以感受和代入为主干，逻辑服务于情绪。
- 行动引导型：以改变行为为目标，洞察服务于方法。

叙事视角（选一个，全文统一）：
- 以“你”为主：读者是主体，作者退后。
- 以“我”为主：作者是主体，读者跟随。
- 混合型：开头用“我”入场，正文切换到“你”。

结尾基调（选一个）：
- 开放式：留问题给读者，不收口。
- 结论式：给出明确判断，有力落地。
- 行动式：以一个具体指令结束。

第三步：执行改稿
这不是润色，而是重构。请按以下原则改写：

编辑判断：
1. 从原文中找出 3 个候选的“最强素材”：意外事实、反常识事实、鲜明矛盾、具体代价、关键变化或未解问题。
2. 比较它们的意外程度、具体程度和与读者现实的距离，只选择最有核心张力的一个。
3. 如果提供了聚焦角度，把它当作观察镜头，而不是把文章写成对读者痛点的训话。
4. 其余素材只在能增强核心张力时使用，不要面面俱到。

概念处理：
1. 每一个引入的概念必须被用起来，不能借来就丢。
2. 专业术语要么解释，要么换成读者能直接理解的表达。
3. 删除所有听起来像口号但没有内容支撑的句子。
4. 不要编造原文没有的信息，不要把原文没有的方法论强行塞进去。

逻辑链条：
1. 每一个转折都要有过渡，不能跳跃。
2. 核心论点不能一句话带过，要展开到读者真正被说服。
3. 如果有建议或练习，它必须从前面的论述里生长出来，不能像附录一样贴上去。
4. 允许有暂时性的判断和不确定性，不要把复杂问题包装成万能答案。
5. 文章要能看见作者思考过程，而不是只给读者一个整理好的结论。

标题与开头：
1. 标题必须包含一个具体对象、变化或矛盾，让人一眼看出文章独有的信息。
2. 优先使用“看似 A，实际 B”“发生了 X，却带来 Y”“一个细节改变了我的判断”等真实张力。
3. 标题要克制，但不能含糊和平淡；禁止标题党，禁止“揭秘/震惊/你必须知道/真正厉害的人”等廉价词。
4. 开头不超过三段就进入核心，前 120 字内亮出最强素材和核心张力，不能慢热或泛泛铺垫。

语言层面：
1. 删除所有励志腔：燃料、觉醒、改写人生等。
2. 删除所有冗余的情绪铺垫：相信我、说真的、我必须承认等。
3. 不要演播腔、鸡汤腔、导师腔、AI 总结腔。
4. 不要说“本文将”“接下来我们”“总之”“综上所述”。
5. 每一段的第一句要能独立成立，不依赖上下文也能看懂。
6. 结尾最后一句要有重量，读完之后有停顿感。

结构层面：
1. 用空行或分隔线替代小标题，除非内容真的需要导航。
2. 段落长度要有节奏变化，避免连续长段或连续短句。
3. 至少包含 2 个来自原文的具体素材，支撑自己的观察。
4. 删除任何拿掉后不影响核心张力的空泛段落。

反训诫约束：
1. 不要批评读者，不要把读者放在被教育的位置。
2. 不要使用“你应该”“你必须”“你是不是”“很多人错就错在”等压迫性表达。
3. 不要输出行动清单，除非原文真的在讲具体方法。
4. 不要把普通经验上升成宏大人生道理。
5. 避免“认知升级”“底层逻辑”“长期主义”“普通人逆袭”等套话。

第四步：输出
请严格按以下格式输出：

【改稿诊断】
- 核心主张：
- 主调选择：
- 叙事视角：
- 结尾基调：
- 重构方向：

【改后全文】
标题

正文

不要解释每一处改动。诊断只说明判断和方向；改后全文要完整可发布。全文 800-1200 字。

文章内容：
{text[:8000]}"""
        max_tokens = 3600
        system_prompt = (
            "你是有编辑判断力的资深内容编辑，擅长先诊断文章主张、主调、视角与结尾，再重构成可发布短文。"
            "你能从素材中识别最有张力的事实、"
            "矛盾与代价，并写成克制、具体、能看见作者思考过程的公众号短文。"
            "不要训诫读者，严格输出【改稿诊断】和【改后全文】。"
        )

    return prompt, max_tokens, system_prompt


def generate_social_post(text: str, format_type: str = "wechat", pain_point: str = "") -> str | None:
    """Generate social media content from article text.
    format_type: 'wechat' | 'insight' | 'list'
    """
    client = _get_client()
    if not client:
        return None

    prompt, max_tokens, system_prompt = _build_social_post_prompt(text, format_type, pain_point)

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.8,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"DeepSeek API Error (generate_social_post): {e}")
        return None


def suggest_pain_points(text: str) -> list[str]:
    """Return 5 concrete pain-point angles for social content, as a list."""
    client = _get_client()
    if not client:
        return []
    try:
        import json as _json
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是内容策略师。只输出合法JSON字符串数组，不输出其他任何内容。"},
                {"role": "user", "content": (
                    "请从以下文章中提炼 5 个有传播张力的内容切入角度。\n"
                    "这些角度将用于生成公众号/小红书内容。\n\n"
                    "要求：\n"
                    "1. 每个角度 15-28 字。\n"
                    "2. 优先选择鲜明矛盾、意外事实、关键变化、具体代价或未解问题。\n"
                    "3. 角度之间要明显不同，避免同义重复。\n"
                    "4. 不要抽象词堆砌，例如“提升认知”“实现成长”。\n"
                    "5. 不要只制造焦虑，不要把读者写成需要被教育的人。\n"
                    "6. 直接输出 JSON 字符串数组，例如：[\"角度1\", \"角度2\"]。\n\n"
                    f"文章内容：\n{text[:4000]}"
                )},
            ],
            max_tokens=300,
            temperature=0.7,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        arr = _json.loads(raw)
        return [s for s in arr if isinstance(s, str)][:5]
    except Exception as e:
        print(f"DeepSeek API Error (suggest_pain_points): {e}")
        return []


def batch_generate_cards(text: str, count: int = 4) -> list[str]:
    """Generate `count` distinct insight card texts from different angles."""
    client = _get_client()
    if not client:
        return []
    try:
        import json as _json
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是内容创作专家。只输出合法JSON字符串数组，不输出其他任何内容。"},
                {"role": "user", "content": (
                    f"请从以下文章中提炼 {count} 条适合做传播卡片的洞见。\n\n"
                    "要求：\n"
                    "1. 每条 25-55 字，独立完整。\n"
                    "2. 每条都必须有明确判断，不要只是主题词或摘要。\n"
                    "3. 角度各不相同，优先选择反直觉、发人深省、能促使转发的句子。\n"
                    "4. 避免空话、鸡汤、标题党。\n"
                    "5. 不要编造原文没有的信息。\n"
                    "6. 直接输出 JSON 字符串数组，例如：[\"洞见1\", \"洞见2\"]。\n\n"
                    f"文章内容：\n{text[:5000]}"
                )},
            ],
            max_tokens=600,
            temperature=0.8,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        arr = _json.loads(raw)
        return [s for s in arr if isinstance(s, str)][:count]
    except Exception as e:
        print(f"DeepSeek API Error (batch_generate_cards): {e}")
        return []


def refine_atomic_note(text: str) -> str | None:
    """Distill a highlighted passage into a single atomic note in Chinese."""
    client = _get_client()
    if not client:
        return None
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是知识管理助手。你只输出一条中文原子笔记，不加标题、前缀或解释。"},
                {"role": "user", "content": (
                    "请把以下高亮内容精炼成一条原子笔记。\n"
                    "要求：\n"
                    "1. 20-60字。\n"
                    "2. 一个独立完整的知识点，脱离原文也能理解。\n"
                    "3. 保留具体判断或因果关系，不要写成主题标签。\n"
                    "4. 不要编造原文没有的信息。\n\n"
                    f"高亮内容：\n{text[:1000]}"
                )},
            ],
            max_tokens=120,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"DeepSeek API Error (refine_atomic_note): {e}")
        return None


def find_related_articles(current_title: str, highlights: list[str], candidates: list[dict]) -> list[dict]:
    """Return up to 5 related articles based on current article's highlights.
    candidates: list of {id, title, summary, tags}
    Returns: list of {id, title, reason}
    """
    client = _get_client()
    if not client or not candidates or not highlights:
        return []

    highlights_str = "\n".join(f"- {h[:120]}" for h in highlights[:10])
    cands_str = "\n".join(
        f"{i+1}. [{c['id']}] 《{c['title']}》: {(c.get('summary') or '')[:80]}"
        for i, c in enumerate(candidates[:20])
    )

    prompt = f"""任务：根据用户在当前文章里的高亮，判断哪些候选文章最相关。

当前文章：《{current_title}》

用户高亮的知识点：
{highlights_str}

候选文章（格式：序号. [id] 《标题》: 摘要）：
{cands_str}

选择规则：
1. 只从候选文章里选，不能编造 id。
2. 优先选择与高亮内容存在概念关联、因果关联、反例关系或可互相解释的文章。
3. 不要只因为标题字面相似就选择。
4. 最多 5 篇；如果没有强相关，可以少于 5 篇。
5. reason 必须 15 字内，说明具体关联点。

输出格式：严格输出合法 JSON 数组，不要 Markdown，不要解释。
[{{"id": "文章id", "reason": "关联原因（15字内）"}}]
"""

    try:
        import json as _json
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是知识图谱助手。你只输出合法 JSON 数组，不输出任何其他内容。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        arr = _json.loads(raw)
        id_to_cand = {c['id']: c for c in candidates}
        result = []
        for item in arr:
            cand = id_to_cand.get(item.get('id', ''))
            if cand:
                result.append({'id': cand['id'], 'title': cand['title'], 'reason': item.get('reason', '')})
        return result[:5]
    except Exception as e:
        print(f"DeepSeek API Error (find_related_articles): {e}")
        return []


def translate_full_article(text: str) -> tuple[str, list[str]]:
    """Translate a full English article to Chinese using DeepSeek.
    Short texts (<=6000 chars) use a single call; longer texts are chunked.
    Returns (zh_text, tags).
    """
    SINGLE_CALL_LIMIT = 3000
    CHUNK_SIZE = 3000

    if len(text) <= SINGLE_CALL_LIMIT:
        result = literal_translate(text)
        if result:
            return result
        return text, []

    # Chunk and translate
    chunks = chunk_text(text, chunk_size=CHUNK_SIZE)
    total = len(chunks)
    parts = []
    for i, chunk in enumerate(chunks):
        translated = literal_translate_chunk(chunk, i, total)
        if translated:
            # Remove the "接下来，" transition prefix added by literal_translate_chunk
            if i > 0 and translated.startswith("接下来，"):
                translated = translated[4:]
            parts.append(translated)
        else:
            parts.append(chunk)  # fallback: keep original

    # Generate tags from title + first chunk
    tags = generate_tags("", chunks[0])
    return "\n\n".join(parts), tags


def generate_tags(title: str, text_sample: str) -> list[str]:
    """Lightweight call to generate tags for long chunked content."""
    client = _get_client()
    if not client:
        return []
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是内容分类助手。只输出标签，逗号分隔，不输出其他任何内容。"},
                {"role": "user", "content": (
                    "请根据以下标题和内容片段生成中文关键词标签。\n\n"
                    "要求：\n"
                    "1. 输出 3-6 个标签，用中文逗号或英文逗号分隔。\n"
                    "2. 标签应是可复用的知识主题，不要太长。\n"
                    "3. 优先选择人物、领域、核心概念、方法论、事件类型。\n"
                    "4. 不要输出句子，不要加 #，不要解释。\n\n"
                    f"标题：{title}\n内容：{text_sample[:2000]}"
                )}
            ],
            max_tokens=60,
            temperature=0.3
        )
        raw = response.choices[0].message.content.strip()
        return [t.strip().lstrip("#").strip() for t in re.split(r'[,，]', raw) if t.strip()][:8]
    except Exception as e:
        print(f"DeepSeek tag generation error: {e}")
        return []
