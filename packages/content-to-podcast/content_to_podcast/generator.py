from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal

from services.extractor import download_youtube_audio, extract_content
from services.llm import (
    CHUNK_THRESHOLD,
    chunk_text,
    detect_language,
    distill_and_translate,
    format_transcript,
    generate_tags,
    generate_title,
    polish_chunk,
)
from services.tts import generate_audio_sync

SourceType = Literal["url", "youtube", "pdf", "txt"]
StatusCallback = Callable[[str, str, dict | None], None]
MAX_PAGES_AUDIO_BYTES = 24 * 1024 * 1024
AUDIO_BITRATES = ("96k", "64k")


@dataclass
class PodcastGenerationOptions:
    source: str
    source_type: SourceType
    title: str = ""
    base_url: str = "http://localhost:8000"
    voice: str = "zh-CN-YunxiNeural"
    use_original_audio: bool = False
    scripts_dir: str = "static/scripts"
    transcripts_dir: str = "static/transcripts"
    audio_dir: str = "static/audio"
    images_dir: str = "static/images"


@dataclass
class GeneratedPodcastItem:
    title: str
    description: str
    script_url: str
    transcript_url: str
    audio_filename: str
    audio_url: str
    audio_length: int
    audio_mime: str = "audio/mpeg"
    image_url: str | None = None
    word_count: int = 0
    tags: list[str] = field(default_factory=list)


@dataclass
class PodcastGenerationResult:
    title: str
    source_url: str | None
    source_type: SourceType
    transcript_url: str
    image_url: str | None
    items: list[GeneratedPodcastItem]
    tags: list[str] = field(default_factory=list)


def _notify(callback: StatusCallback | None, status: str, message: str, file: dict | None = None) -> None:
    if callback:
        callback(status, message, file)


def sanitize_filename(title: str) -> str:
    safe = re.sub(r"[^\w\u4e00-\u9fff]", "_", title)
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe[:50] or "untitled"


def clean_description(text: str) -> str:
    text = re.sub(r"<\d+:\d+:\d+\.\d+>", "", text)
    text = re.sub(r"</?c>", "", text)
    text = re.sub(r"Kind:\s*captions\s*Language:\s*\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _local_url(path: str) -> str:
    return "/" + path.replace(os.sep, "/").lstrip("/")


def download_thumbnail(thumbnail_url: str | None, images_dir: str) -> str | None:
    if not thumbnail_url:
        return None
    os.makedirs(images_dir, exist_ok=True)
    try:
        req = urllib.request.Request(thumbnail_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            content_type = resp.headers.get_content_type() or "image/jpeg"
            ext = "png" if "png" in content_type else "jpg"
            filename = f"{uuid.uuid4().hex}.{ext}"
            path = os.path.join(images_dir, filename)
            with open(path, "wb") as f:
                f.write(resp.read())
        return _local_url(path)
    except Exception as e:
        print(f"Failed to download thumbnail: {e}")
        return None


def save_transcript(title: str, text: str, source_type: SourceType, transcripts_dir: str) -> str:
    os.makedirs(transcripts_dir, exist_ok=True)
    lang = detect_language(text)
    lang_label = "中文" if lang == "zh" else "英文"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{sanitize_filename(title)}_逐字稿_{ts}.md"
    path = os.path.join(transcripts_dir, filename)
    note = "" if lang == "zh" else "\n\n> 英文原稿，中文播客文稿见对应的文稿文件。"
    content = f"""# {title} - 原始逐字稿

**来源类型**: {source_type}
**处理时间**: {datetime.now().strftime("%Y-%m-%d %H:%M")}
**原文语言**: {lang_label}
{note}

---

{text}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return _local_url(path)


def save_script(title: str, script: str, scripts_dir: str, part_label: str = "") -> str:
    os.makedirs(scripts_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    part_suffix = f"_{part_label}" if part_label else ""
    filename = f"{sanitize_filename(title)}{part_suffix}_{ts}.md"
    path = os.path.join(scripts_dir, filename)
    display_title = f"{title} {part_label}".strip()
    content = f"""# {display_title}

**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

{script}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return _local_url(path)


def _transcode_audio(input_path: str, output_path: str, bitrate: str) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("未找到 ffmpeg，无法压缩音频。请安装 ffmpeg 后重试。")

    cmd = [
        ffmpeg,
        "-y",
        "-i",
        input_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "44100",
        "-b:a",
        bitrate,
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"ffmpeg 压缩音频失败：{detail[-500:]}")


def normalize_audio_for_podcast(audio_filename: str, audio_dir: str) -> str:
    """Transcode audio for podcast hosting limits. Returns the final filename."""
    source_path = os.path.join(audio_dir, audio_filename)
    if not os.path.exists(source_path):
        raise RuntimeError(f"音频文件不存在：{source_path}")

    stem, _ = os.path.splitext(audio_filename)
    final_filename = f"{stem}.mp3"
    final_path = os.path.join(audio_dir, final_filename)
    original_path = source_path

    for bitrate in AUDIO_BITRATES:
        tmp_path = os.path.join(audio_dir, f"_tmp_{uuid.uuid4().hex}.mp3")
        _transcode_audio(original_path, tmp_path, bitrate)
        size = os.path.getsize(tmp_path)

        if original_path != final_path and os.path.exists(final_path):
            os.remove(final_path)
        os.replace(tmp_path, final_path)

        if original_path != final_path and os.path.exists(original_path):
            os.remove(original_path)

        original_path = final_path
        if size <= MAX_PAGES_AUDIO_BYTES:
            return final_filename

    size_mb = os.path.getsize(final_path) / (1024 * 1024)
    raise RuntimeError(
        f"音频压缩到 64kbps 后仍有 {size_mb:.1f} MiB，超过 Cloudflare Pages 限制。"
        "请把内容分段后再生成。"
    )


def _make_item(
    *,
    title: str,
    source_text: str,
    script: str,
    script_url: str,
    transcript_url: str,
    audio_filename: str,
    base_url: str,
    image_url: str | None,
    tags: list[str],
    audio_dir: str,
    audio_mime: str = "audio/mpeg",
) -> GeneratedPodcastItem:
    audio_path = os.path.join(audio_dir, audio_filename)
    return GeneratedPodcastItem(
        title=title,
        description=clean_description(source_text[:300]) + "...",
        script_url=script_url,
        transcript_url=transcript_url,
        audio_filename=audio_filename,
        audio_url=f"{base_url}/static/audio/{audio_filename}",
        audio_length=os.path.getsize(audio_path),
        audio_mime=audio_mime,
        image_url=image_url,
        word_count=len(script),
        tags=tags,
    )


def generate_podcast(
    options: PodcastGenerationOptions,
    on_status: StatusCallback | None = None,
) -> PodcastGenerationResult:
    source_url = options.source if options.source_type in ("url", "youtube") else None

    _notify(on_status, "extracting", "正在提取内容...")
    text, thumbnail_url = extract_content(options.source, options.source_type)
    if not text:
        raise ValueError("内容提取失败，请检查链接或文件。")

    title = options.title.strip()
    if not title:
        _notify(on_status, "extracting", "正在生成标题...")
        title = generate_title(text)

    image_url = download_thumbnail(thumbnail_url, options.images_dir)
    transcript_url = save_transcript(title, text, options.source_type, options.transcripts_dir)
    _notify(on_status, "processing", "正在保存逐字稿...", {
        "label": "原始逐字稿",
        "url": transcript_url,
    })

    items: list[GeneratedPodcastItem] = []
    tags: list[str] = []

    if options.use_original_audio and options.source_type == "youtube":
        _notify(on_status, "processing", "正在整理文字稿...")
        result = format_transcript(text)
        if not result:
            raise RuntimeError("LLM 处理失败，请检查 API Key。")
        script, tags = result
        script_url = save_script(title, script, options.scripts_dir)
        _notify(on_status, "generating_audio", "正在下载原始音频...", {
            "label": "播客文稿",
            "url": script_url,
        })
        audio_filename = download_youtube_audio(options.source, options.audio_dir)
        if not audio_filename:
            raise RuntimeError("原始音频下载失败，请检查链接。")
        _notify(on_status, "generating_audio", "正在压缩音频为 96kbps mono...")
        audio_filename = normalize_audio_for_podcast(audio_filename, options.audio_dir)
        items.append(_make_item(
            title=title,
            source_text=text,
            script=script,
            script_url=script_url,
            transcript_url=transcript_url,
            audio_filename=audio_filename,
            base_url=options.base_url,
            image_url=image_url,
            tags=tags,
            audio_dir=options.audio_dir,
        ))
    elif len(text) <= CHUNK_THRESHOLD:
        _notify(on_status, "processing", "正在使用 DeepSeek 处理内容...")
        result = distill_and_translate(text)
        if not result:
            raise RuntimeError("LLM 处理失败，请检查 API Key。")
        script, tags = result
        script_url = save_script(title, script, options.scripts_dir)
        _notify(on_status, "generating_audio", "正在生成音频...", {
            "label": "播客文稿",
            "url": script_url,
        })
        audio_filename = generate_audio_sync(script, voice=options.voice, output_dir=options.audio_dir)
        _notify(on_status, "generating_audio", "正在压缩音频为 96kbps mono...")
        audio_filename = normalize_audio_for_podcast(audio_filename, options.audio_dir)
        items.append(_make_item(
            title=title,
            source_text=text,
            script=script,
            script_url=script_url,
            transcript_url=transcript_url,
            audio_filename=audio_filename,
            base_url=options.base_url,
            image_url=image_url,
            tags=tags,
            audio_dir=options.audio_dir,
        ))
    else:
        chunks = chunk_text(text)
        total = len(chunks)
        _notify(on_status, "processing", f"内容较长，分为 {total} 段处理...")
        tags = generate_tags(title, chunks[0]) if chunks else []

        for i, chunk in enumerate(chunks):
            part_label = f"第{i + 1}段_共{total}段"
            part_display = f"（第{i + 1}段/共{total}段）"
            part_title = f"{title} {part_display}"
            _notify(on_status, "processing", f"正在处理第 {i + 1}/{total} 段...")
            polished = polish_chunk(chunk, i, total)
            if not polished:
                print(f"Skipping part {i + 1} due to LLM error.")
                continue

            script_url = save_script(title, polished, options.scripts_dir, part_label)
            _notify(on_status, "generating_audio", f"正在生成第 {i + 1}/{total} 段音频...", {
                "label": f"播客文稿 {part_display}",
                "url": script_url,
            })
            audio_filename = generate_audio_sync(polished, voice=options.voice, output_dir=options.audio_dir)
            _notify(on_status, "generating_audio", f"正在压缩第 {i + 1}/{total} 段音频为 96kbps mono...")
            audio_filename = normalize_audio_for_podcast(audio_filename, options.audio_dir)
            items.append(_make_item(
                title=part_title,
                source_text=chunk,
                script=polished,
                script_url=script_url,
                transcript_url=transcript_url,
                audio_filename=audio_filename,
                base_url=options.base_url,
                image_url=image_url,
                tags=tags,
                audio_dir=options.audio_dir,
            ))

    if not items:
        raise RuntimeError("没有成功生成任何音频或文稿。")

    return PodcastGenerationResult(
        title=title,
        source_url=source_url,
        source_type=options.source_type,
        transcript_url=transcript_url,
        image_url=image_url,
        items=items,
        tags=tags,
    )
