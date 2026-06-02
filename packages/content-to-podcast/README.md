# Content to Podcast

独立的内容转播客工具包。它负责把网页、YouTube、抖音、B站、微信公众号、PDF、TXT 转成：

- 原始逐字稿 Markdown
- 中文播客文稿 Markdown
- MP3 音频
- 标题、标签、封面图等结构化结果

Second Brain 现在通过 `generate_podcast()` 调用这个包。后续优化这里的生成流程，会直接影响 Second Brain 的播客生成效果。

## 默认生成原则

默认模式优先忠于原文：保留原始观点、顺序、案例、数据和推理，只清理字幕噪音、重复口癖和断裂表达。不要把 10-20 分钟的视频压缩成摘要版播客。

实现上：

- 短内容走 `format_transcript()`：整理/翻译为中文 Markdown，不做蒸馏摘要。
- 长内容超过 `CHUNK_THRESHOLD` 后分段走 `polish_chunk()`：逐段忠实整理，并生成多段音频。
- `distill_and_translate()` 是摘要模式，不是默认播客生成路径。

在 Web 表单中勾选「摘要」，或在 CLI 中使用 `--summarize`，才会走摘要模式。

## 当前边界

当前版本已经把生成编排层封装成独立包，并提供 Python API 与命令行入口。底层能力仍默认复用 Second Brain 仓库已有模块：

- `services.extractor`
- `services.llm`
- `services.tts`

这些依赖现在是延迟加载的：你可以单独 import `content_to_podcast`、查看类型、接入自定义 adapter，不会在 import 阶段因为找不到 `services.*` 失败。实际生成时，如果不传自定义 services，仍需要在 Second Brain 仓库环境内运行。

## 命令行用法

在 Second Brain 仓库内安装本地包：

```bash
pip install -e packages/content-to-podcast
```

生成播客：

```bash
content-to-podcast "https://example.com/article" --type url
```

生成摘要版播客：

```bash
content-to-podcast "https://example.com/article" --type url --summarize
```

视频平台使用原音频：

```bash
content-to-podcast "https://www.youtube.com/watch?v=xxxx" --type youtube --use-original-audio
content-to-podcast "https://www.bilibili.com/video/BVxxxx" --type bilibili --use-original-audio
content-to-podcast "https://www.douyin.com/video/xxxx" --type douyin --use-original-audio
```

如果不传 `--type`，工具会自动识别 YouTube、抖音、B站、微信公众号和普通网页。

注意：抖音短链可能会过期，或在没有登录/cookie 的环境下只跳转到抖音首页。遇到这种情况，需要换成有效作品页链接，或在本机浏览器登录后再试。

常用参数：

- `--title`：手动指定标题
- `--voice`：指定 Edge TTS 声音
- `--output-dir`：指定输出根目录，默认 `static`
- `--base-url`：生成结果里的公开 URL 前缀
- `--json`：输出完整结构化结果

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

## 自定义底层服务

如果未来要脱离 Second Brain 使用，可以传入 `PodcastGenerationServices`，替换内容提取、LLM、TTS 等能力：

```python
from content_to_podcast import PodcastGenerationOptions, PodcastGenerationServices, generate_podcast

services = PodcastGenerationServices(
    extract_content=my_extract_content,
    download_youtube_audio=my_download_youtube_audio,
    generate_audio_sync=my_generate_audio_sync,
    detect_language=my_detect_language,
    generate_title=my_generate_title,
    format_transcript=my_format_transcript,
    distill_and_translate=my_distill_and_translate,
    chunk_text=my_chunk_text,
    polish_chunk=my_polish_chunk,
    generate_tags=my_generate_tags,
    chunk_threshold=12000,
)

result = generate_podcast(
    PodcastGenerationOptions(
        source="https://example.com/article",
        source_type="url",
        services=services,
    )
)
```

## 优化方向

- 增加不同文稿风格，例如忠实版、精简版、深度版、访谈版
- 统一输出 ZIP 包
- 增加独立 Web UI
- 增加用例测试和示例输入
- 将提取、LLM、TTS 底层模块迁入本包
