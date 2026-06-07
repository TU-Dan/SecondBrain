from __future__ import annotations

import argparse
import json
from pathlib import Path

from .generator import PodcastGenerationOptions, SourceType, generate_podcast


def _detect_source_type(source: str) -> SourceType:
    lower = source.lower()
    if lower.endswith(".pdf"):
        return "pdf"
    if lower.endswith(".txt") or Path(source).suffix.lower() in {".md", ".markdown"}:
        return "txt"
    if "youtube.com" in lower or "youtu.be" in lower:
        return "youtube"
    if "douyin.com" in lower or "iesdouyin.com" in lower:
        return "douyin"
    if "bilibili.com" in lower or "b23.tv" in lower:
        return "bilibili"
    if "mp.weixin.qq.com" in lower:
        return "wechat"
    return "url"


def _print_status(status: str, message: str, file: dict | None = None) -> None:
    suffix = f" -> {file.get('url')}" if file and file.get("url") else ""
    print(f"[{status}] {message}{suffix}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="content-to-podcast",
        description="Turn a URL, YouTube video, PDF, or text file into podcast script and MP3 audio.",
    )
    parser.add_argument("source", help="URL or local file path")
    parser.add_argument("--type", choices=["url", "youtube", "douyin", "bilibili", "wechat", "pdf", "txt"], dest="source_type")
    parser.add_argument("--title", default="", help="Optional podcast title")
    parser.add_argument("--voice", default="zh-CN-YunxiNeural", help="Edge TTS voice name")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Public base URL for generated file links")
    parser.add_argument("--output-dir", default="static", help="Output root directory")
    parser.add_argument("--use-original-audio", action="store_true", help="Use original YouTube audio instead of generated TTS")
    parser.add_argument("--summarize", action="store_true", help="Use concise summary mode instead of faithful transcript mode")
    parser.add_argument("--force-transcribe", action="store_true", help="Ignore platform subtitles and run Faster-Whisper")
    parser.add_argument("--json", action="store_true", help="Print the full result as JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source_type = args.source_type or _detect_source_type(args.source)
    output_root = Path(args.output_dir)

    result = generate_podcast(
        PodcastGenerationOptions(
            source=args.source,
            source_type=source_type,
            title=args.title,
            base_url=args.base_url.rstrip("/"),
            voice=args.voice,
            use_original_audio=args.use_original_audio,
            summarize=args.summarize,
            force_transcribe=args.force_transcribe,
            scripts_dir=str(output_root / "scripts"),
            transcripts_dir=str(output_root / "transcripts"),
            audio_dir=str(output_root / "audio"),
            images_dir=str(output_root / "images"),
        ),
        on_status=_print_status,
    )

    payload = {
        "title": result.title,
        "source_url": result.source_url,
        "source_type": result.source_type,
        "transcript_url": result.transcript_url,
        "transcript_source": result.transcript_source,
        "image_url": result.image_url,
        "tags": result.tags,
        "warnings": result.warnings,
        "items": [item.__dict__ for item in result.items],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"\nGenerated {len(result.items)} podcast item(s):")
        for item in result.items:
            print(f"- {item.title}")
            print(f"  script: {item.script_url}")
            print(f"  audio:  {item.audio_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
