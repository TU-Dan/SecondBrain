from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from content_to_podcast.source_adapters import (
    BilibiliAdapter,
    DouyinAdapter,
    PreparedSource,
    SourcePreparationError,
    _finish_video_source,
    create_work_dir,
)
from services.extractor import (
    ExtractionError,
    download_youtube_audio,
    extract_content,
    extract_from_wechat,
    extract_from_url,
    extract_from_youtube,
    normalize_video_url,
)


def _title_from_text(text: str, fallback: str) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return first_line[:160] or fallback


def prepare_source(
    source: str,
    source_type: str,
    on_status: Callable | None = None,
    force_transcribe: bool = False,
) -> PreparedSource:
    if source_type == "douyin":
        return DouyinAdapter().prepare(source, create_work_dir("douyin"), on_status, force_transcribe)
    if source_type == "bilibili":
        return BilibiliAdapter().prepare(source, create_work_dir("bilibili"), on_status, force_transcribe)
    if source_type == "youtube":
        return _prepare_youtube(source, on_status, force_transcribe)
    if source_type == "wechat":
        text, thumbnail = extract_from_wechat(source)
        return _article_source(source, source_type, text, thumbnail)
    if source_type == "url":
        text, thumbnail = extract_from_url(source)
        return _article_source(source, source_type, text, thumbnail)
    if source_type in {"pdf", "txt"}:
        text, thumbnail = extract_content(source, source_type)
        return PreparedSource(
            source_type=source_type,
            original_url=source,
            canonical_url=source,
            title=Path(source).stem,
            text=text,
            transcript_source="article",
            thumbnail_url=thumbnail,
        )
    raise SourcePreparationError(f"不支持的来源类型：{source_type}", "platform_download_failed")


def _article_source(source: str, source_type: str, text: str, thumbnail: str | None) -> PreparedSource:
    if not text:
        raise SourcePreparationError("无法提取文章正文。", "platform_download_failed")
    return PreparedSource(
        source_type=source_type,
        original_url=source,
        canonical_url=source,
        title=_title_from_text(text, "未命名内容"),
        text=text,
        transcript_source="article",
        thumbnail_url=thumbnail,
    )


def _prepare_youtube(source: str, on_status: Callable | None, force_transcribe: bool = False) -> PreparedSource:
    canonical = normalize_video_url(source)
    try:
        text, thumbnail = extract_from_youtube(canonical)
    except ExtractionError as exc:
        raise SourcePreparationError(str(exc), "cookie_required" if "验证" in str(exc) else "platform_download_failed") from exc

    title = _title_from_text(text, "YouTube 视频")
    marker = "视频字幕/转写："
    transcript = text.split(marker, 1)[1].split("视频简介：", 1)[0].strip() if marker in text else ""
    if len(transcript) >= 200 and not force_transcribe:
        return PreparedSource(
            source_type="youtube",
            original_url=source,
            canonical_url=canonical,
            title=title,
            text=text,
            transcript_source="platform_subtitle",
            thumbnail_url=thumbnail,
        )

    work_dir = create_work_dir("youtube")
    if on_status:
        on_status("downloading", "YouTube 没有可用字幕，正在下载音频...", None)
    audio_filename = download_youtube_audio(canonical, work_dir)
    if not audio_filename:
        raise SourcePreparationError("YouTube 音频下载失败。", "platform_download_failed")
    audio_path = os.path.join(work_dir, audio_filename)
    prepared = _finish_video_source(
        source_type="youtube",
        original_url=source,
        canonical_url=canonical,
        title=title,
        thumbnail_url=thumbnail,
        media_path=audio_path,
        work_dir=work_dir,
        on_status=on_status,
        force_transcribe=force_transcribe,
    )
    if text:
        prepared.warnings.append("平台无有效字幕，已使用 Faster-Whisper 转录。")
    return prepared
