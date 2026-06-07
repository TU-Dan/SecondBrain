# Content to Podcast

独立的内容转播客工具包。它负责把网页、YouTube、抖音、B站、微信公众号、PDF、TXT 转成：

- 原始逐字稿 Markdown
- 中文文章文稿 Markdown
- 可选的分段播客文稿 Markdown
- MP3 音频
- 标题、标签、封面图等结构化结果

Second Brain 现在通过 `generate_podcast()` 调用这个包。后续优化这里的生成流程，会直接影响 Second Brain 的播客生成效果。

## 默认生成原则

默认模式优先忠于原文：保留原始观点、顺序、案例、数据和推理，只清理字幕噪音、重复口癖和断裂表达。不要把 10-20 分钟的视频压缩成摘要版播客。

实现上：

- 短内容走 `format_transcript()`：整理/翻译为中文 Markdown，不做蒸馏摘要。
- 长内容超过 `CHUNK_THRESHOLD` 后分段走 `polish_chunk()`：逐段忠实整理并生成多段音频；同时合并保存一篇完整文章文稿，供知识库阅读和检索使用。
- `distill_and_translate()` 是摘要模式，不是默认播客生成路径。

也就是说，长内容在 RSS/播客里可以是多段 episode，但在 Second Brain 的文章库里应该只是一篇完整文章。

在 Web 表单中勾选「摘要」，或在 CLI 中使用 `--summarize`，才会走摘要模式。

## 当前边界

当前版本已经把生成编排层封装成独立包，并提供 Python API 与命令行入口。默认运行链路由以下能力组成：

- `DouyinAdapter`：调用本机 Douyin Downloader 服务
- `BilibiliAdapter`：调用本机 BBDown
- `YouTubeAdapter`：继续使用 `yt-dlp`
- `Faster-Whisper`：视频没有有效字幕时自动转录
- `services.podcast_sources`：将平台结果统一为 `PreparedSource`
- `services.llm`
- `services.tts`

这些依赖是延迟加载的：你可以单独 import `content_to_podcast`、查看类型、接入自定义 adapter，不会在 import 阶段因为找不到 `services.*` 失败。实际生成时，如果不传自定义 services，仍需要在 Second Brain 仓库环境内运行。

## Mac 本地准备

安装 BBDown、Douyin Downloader 与 Faster-Whisper：

```bash
bash scripts/setup_podcast_tools_macos.sh
```

生成抖音播客前，另开一个终端启动专用下载服务：

```bash
bash scripts/start_douyin_downloader.sh
```

B站公开内容默认无需 Cookie。遇到登录验证时，将浏览器 Cookie 字符串写入：

```text
data/cookies/bilibili.txt
```

抖音出现 `cookie_required` 或反爬验证时，获取并写入最新浏览器 Cookie：

```bash
bash scripts/capture_douyin_cookie.sh
```

登录完成后，重启 `scripts/start_douyin_downloader.sh`。

视频转录默认使用 `small + CPU int8`，模型缓存位于 `data/models/`。可以通过 `.env` 调整：

```env
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_HF_ENDPOINT=https://hf-mirror.com
```

需要忽略平台字幕并重新转录时，可在任务 API 中传入 `force_transcribe=true`，或在 CLI 中使用 `--force-transcribe`。

生成任务会写入 SQLite `podcast_jobs` 队列，由单 worker 顺序执行。服务重启后，中断任务会自动回到等待队列。

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

注意：抖音短链可能会过期，或只跳转到抖音首页。遇到这种情况会返回 `expired_share_link`；需要重新复制有效作品链接。

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

print(result.article_script_url)  # 知识库使用的完整文章文稿
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
