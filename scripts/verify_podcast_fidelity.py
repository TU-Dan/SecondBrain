#!/usr/bin/env python3
"""Verify podcast generation uses faithful transcript paths by default.

This is a lightweight regression harness with fake services. It does not call
LLM, TTS, or network APIs.
"""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "packages" / "content-to-podcast"))

import content_to_podcast.generator as generator
from content_to_podcast.generator import (
    PodcastGenerationOptions,
    PodcastGenerationServices,
    generate_podcast,
)


def make_services(source_text: str, calls: list[str]) -> PodcastGenerationServices:
    def extract_content(source, source_type):
        calls.append("extract_content")
        return source_text, None

    def generate_audio_sync(script, voice, audio_dir):
        calls.append("generate_audio_sync")
        Path(audio_dir).mkdir(parents=True, exist_ok=True)
        path = Path(audio_dir) / f"audio-{len(calls)}.mp3"
        path.write_bytes(b"audio")
        return path.name

    def format_transcript(text):
        calls.append("format_transcript")
        return text, ["测试"]

    def distill_and_translate(text):
        calls.append("distill_and_translate")
        return "SHOULD_NOT_USE_SUMMARY_MODE", ["测试"]

    def chunk_text(text):
        calls.append("chunk_text")
        midpoint = len(text) // 2
        return [text[:midpoint], text[midpoint:]]

    def polish_chunk(chunk, part_index, total_parts):
        calls.append(f"polish_chunk_{part_index + 1}")
        return chunk

    return PodcastGenerationServices(
        extract_content=extract_content,
        download_youtube_audio=lambda source, audio_dir: None,
        generate_audio_sync=generate_audio_sync,
        detect_language=lambda text: "zh",
        generate_title=lambda text: "测试播客",
        format_transcript=format_transcript,
        distill_and_translate=distill_and_translate,
        chunk_text=chunk_text,
        polish_chunk=polish_chunk,
        generate_tags=lambda title, text: ["测试"],
        chunk_threshold=12000,
    )


def run_case(source_text: str, summarize: bool = False) -> list[str]:
    calls: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        original_normalize = generator.normalize_audio_for_podcast
        generator.normalize_audio_for_podcast = lambda audio_filename, audio_dir: audio_filename
        try:
            generate_podcast(
                PodcastGenerationOptions(
                    source="fixture",
                    source_type="txt",
                    title="测试播客",
                    scripts_dir=str(root / "scripts"),
                    transcripts_dir=str(root / "transcripts"),
                    audio_dir=str(root / "audio"),
                    images_dir=str(root / "images"),
                    services=make_services(source_text, calls),
                    summarize=summarize,
                )
            )
        finally:
            generator.normalize_audio_for_podcast = original_normalize
    return calls


def main() -> int:
    short_calls = run_case("短文本。" * 100)
    assert "format_transcript" in short_calls, short_calls
    assert "distill_and_translate" not in short_calls, short_calls

    long_calls = run_case("长文本。" * 5000)
    assert "chunk_text" in long_calls, long_calls
    assert "polish_chunk_1" in long_calls and "polish_chunk_2" in long_calls, long_calls
    assert "distill_and_translate" not in long_calls, long_calls

    summary_calls = run_case("摘要文本。" * 100, summarize=True)
    assert "distill_and_translate" in summary_calls, summary_calls

    print("podcast fidelity path ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
