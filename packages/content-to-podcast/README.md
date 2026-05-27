# Content to Podcast

独立的内容转播客工具包。它负责把网页、YouTube、PDF、TXT 转成：

- 原始逐字稿 Markdown
- 中文播客文稿 Markdown
- MP3 音频
- 标题、标签、封面图等结构化结果

Second Brain 现在通过 `generate_podcast()` 调用这个包。后续优化这里的生成流程，会直接影响 Second Brain 的播客生成效果。

## 当前边界

第一阶段只抽出了生成编排层，底层仍复用仓库已有模块：

- `services.extractor`
- `services.llm`
- `services.tts`

后续可以逐步把这些底层能力迁进本包，再单独发布成 GitHub 仓库或 Docker 小工具。

## Python 用法

```python
from content_to_podcast import PodcastGenerationOptions, generate_podcast

result = generate_podcast(
    PodcastGenerationOptions(
        source="https://example.com/article",
        source_type="url",
        title="",
        base_url="http://localhost:8000",
    )
)

for item in result.items:
    print(item.script_url, item.audio_url)
```

## 优化方向

- 增加不同文稿风格，例如精简版、深度版、访谈版
- 统一输出 ZIP 包
- 增加独立 Web UI
- 增加用例测试和示例输入
- 将提取、LLM、TTS 底层模块迁入本包
