from __future__ import annotations

import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages" / "content-to-podcast"))

from content_to_podcast import PodcastGenerationOptions, PodcastGenerationServices, PreparedSource, generate_podcast
from content_to_podcast.source_adapters import (
    DouyinAdapter,
    SourcePreparationError,
    _extract_shared_url,
    _finish_video_source,
)
from content_to_podcast.transcription import TranscriptionResult
from services import db
from services import podcast_jobs
from services.extractor import detect_url_platform


class PlatformDetectionTests(unittest.TestCase):
    def test_detects_supported_platforms(self):
        self.assertEqual(detect_url_platform("https://v.douyin.com/abc"), "douyin")
        self.assertEqual(detect_url_platform("https://www.bilibili.com/video/BV1xx"), "bilibili")
        self.assertEqual(detect_url_platform("https://b23.tv/abc"), "bilibili")
        self.assertEqual(detect_url_platform("https://mp.weixin.qq.com/s/abc"), "wechat")
        self.assertEqual(detect_url_platform("https://example.com"), "url")


class PreparedSourceTests(unittest.TestCase):
    def test_extracts_url_from_douyin_share_text(self):
        shared = "复制打开抖音 https://v.douyin.com/HCgA0KAJm5o/ goq:/"
        self.assertEqual(
            _extract_shared_url(shared, ("douyin.com", "iesdouyin.com")),
            "https://v.douyin.com/HCgA0KAJm5o/",
        )

    def test_douyin_connection_error_is_not_reported_as_expired_link(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
            with self.assertRaises(SourcePreparationError) as raised:
                DouyinAdapter()._submit("https://v.douyin.com/test")
        self.assertEqual(raised.exception.error_code, "platform_download_failed")

    def test_douyin_failed_item_without_detail_requests_cookie(self):
        responses = [
            Mock(__enter__=Mock(return_value=Mock(read=Mock(return_value=b'{"status":"failed","failed":1}'))), __exit__=Mock(return_value=False)),
        ]
        with patch("urllib.request.urlopen", side_effect=responses):
            with self.assertRaises(SourcePreparationError) as raised:
                DouyinAdapter()._poll_task("job-id")
        self.assertEqual(raised.exception.error_code, "cookie_required")
        self.assertIn("Cookie", str(raised.exception))

    def test_platform_subtitle_skips_whisper(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / "source.mp3"
            media.write_bytes(b"audio")
            subtitle = Path(tmp) / "source.srt"
            subtitle.write_text("有效字幕。" * 100, encoding="utf-8")

            with patch("content_to_podcast.source_adapters.transcribe_audio") as transcribe:
                prepared = _finish_video_source(
                    source_type="bilibili",
                    original_url="https://b23.tv/test",
                    canonical_url="https://www.bilibili.com/video/test",
                    title="测试",
                    thumbnail_url=None,
                    media_path=str(media),
                    work_dir=tmp,
                    on_status=None,
                )

            self.assertEqual(prepared.transcript_source, "platform_subtitle")
            transcribe.assert_not_called()

    def test_missing_subtitle_uses_whisper(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / "source.mp3"
            media.write_bytes(b"audio")
            transcription = TranscriptionResult(
                text="转录结果",
                language="zh",
                srt_path=str(Path(tmp) / "source.srt"),
                markdown_path=str(Path(tmp) / "source.md"),
            )
            with patch("content_to_podcast.source_adapters.transcribe_audio", return_value=transcription):
                prepared = _finish_video_source(
                    source_type="douyin",
                    original_url="https://v.douyin.com/test",
                    canonical_url="https://www.douyin.com/video/test",
                    title="测试",
                    thumbnail_url=None,
                    media_path=str(media),
                    work_dir=tmp,
                    on_status=None,
                )

            self.assertEqual(prepared.transcript_source, "whisper")
            self.assertEqual(prepared.text, "转录结果")

    def test_force_transcribe_ignores_platform_subtitle(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / "source.mp3"
            media.write_bytes(b"audio")
            Path(tmp, "source.srt").write_text("有效字幕。" * 100, encoding="utf-8")
            transcription = TranscriptionResult(
                text="重新转录结果",
                language="zh",
                srt_path=str(Path(tmp) / "whisper.srt"),
                markdown_path=str(Path(tmp) / "whisper.md"),
            )
            with patch("content_to_podcast.source_adapters.transcribe_audio", return_value=transcription):
                prepared = _finish_video_source(
                    source_type="bilibili",
                    original_url="https://b23.tv/test",
                    canonical_url="https://www.bilibili.com/video/test",
                    title="测试",
                    thumbnail_url=None,
                    media_path=str(media),
                    work_dir=tmp,
                    on_status=None,
                    force_transcribe=True,
                )

            self.assertEqual(prepared.transcript_source, "whisper")
            self.assertEqual(prepared.text, "重新转录结果")

    def test_cached_whisper_skips_retranscription(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / "source.mp4"
            media.write_bytes(b"video")
            Path(tmp, "source_whisper.md").write_text(
                "# Whisper 转录\n\n---\n\n" + "缓存转录。" * 100,
                encoding="utf-8",
            )
            with patch("content_to_podcast.source_adapters.transcribe_audio") as transcribe:
                prepared = _finish_video_source(
                    source_type="douyin",
                    original_url="https://v.douyin.com/test",
                    canonical_url="https://www.douyin.com/video/test",
                    title="测试",
                    thumbnail_url=None,
                    media_path=str(media),
                    work_dir=tmp,
                    on_status=None,
                )
            self.assertEqual(prepared.transcript_source, "whisper")
            self.assertIn("缓存转录", prepared.text)
            transcribe.assert_not_called()


class GeneratorPreparedSourceTests(unittest.TestCase):
    def test_generator_uses_prepared_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_dir = Path(tmp) / "audio"
            scripts_dir = Path(tmp) / "scripts"
            transcripts_dir = Path(tmp) / "transcripts"
            images_dir = Path(tmp) / "images"

            def generate_audio(text, voice, output_dir):
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                path = Path(output_dir) / "generated.mp3"
                path.write_bytes(b"audio")
                return path.name

            services = PodcastGenerationServices(
                extract_content=lambda source, source_type: ("legacy", None),
                download_youtube_audio=lambda source, output_dir: None,
                generate_audio_sync=generate_audio,
                detect_language=lambda text: "zh",
                generate_title=lambda text: "AI 标题",
                format_transcript=lambda text: ("忠实文稿", ["测试"]),
                distill_and_translate=lambda text: ("摘要", ["测试"]),
                chunk_text=lambda text: [text],
                polish_chunk=lambda text, index, total: text,
                generate_tags=lambda title, text: ["测试"],
                chunk_threshold=1000,
                prepare_source=lambda source, source_type, callback, force_transcribe: PreparedSource(
                    source_type="douyin",
                    original_url=source,
                    canonical_url="https://www.douyin.com/video/test",
                    title="抖音标题",
                    text="完整转录正文",
                    transcript_source="whisper",
                ),
            )
            with patch("content_to_podcast.generator.normalize_audio_for_podcast", side_effect=lambda filename, directory: filename):
                result = generate_podcast(PodcastGenerationOptions(
                    source="https://v.douyin.com/test",
                    source_type="douyin",
                    services=services,
                    audio_dir=str(audio_dir),
                    scripts_dir=str(scripts_dir),
                    transcripts_dir=str(transcripts_dir),
                    images_dir=str(images_dir),
                ))

            self.assertEqual(result.title, "抖音标题")
            self.assertEqual(result.transcript_source, "whisper")
            self.assertEqual(result.source_url, "https://www.douyin.com/video/test")


class PodcastJobPersistenceTests(unittest.TestCase):
    def test_job_claim_and_recovery(self):
        original_path = db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = str(Path(tmp) / "knowledge.db")
            try:
                db.init_db()
                job_id = db.create_podcast_job("https://example.com", "url", {"title": "test"})
                self.assertTrue(db.claim_podcast_job(job_id))
                self.assertFalse(db.claim_podcast_job(job_id))
                self.assertEqual(db.get_podcast_job(job_id)["status"], "running")
                self.assertEqual(db.reset_running_podcast_jobs(), 1)
                self.assertEqual(db.get_podcast_job(job_id)["status"], "pending")
            finally:
                db.DB_PATH = original_path

    def test_worker_completes_persistent_job(self):
        original_path = db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = str(Path(tmp) / "knowledge.db")
            try:
                db.init_db()
                job_id = db.create_podcast_job(
                    "https://example.com/article",
                    "url",
                    {"base_url": "http://localhost:8000"},
                )
                item = SimpleNamespace(
                    title="测试播客",
                    description="测试描述",
                    audio_filename="test.mp3",
                    audio_length=10,
                    image_url=None,
                    audio_mime="audio/mpeg",
                    audio_url="http://localhost:8000/static/audio/test.mp3",
                    script_url="/static/scripts/test.md",
                    transcript_url="/static/transcripts/test.md",
                    word_count=20,
                    tags=[],
                    __dict__={
                        "title": "测试播客",
                        "audio_url": "http://localhost:8000/static/audio/test.mp3",
                    },
                )
                generated = SimpleNamespace(
                    title="测试播客",
                    source_url="https://example.com/article",
                    source_type="url",
                    article_summary="测试描述",
                    article_script_url="/static/scripts/test.md",
                    transcript_url="/static/transcripts/test.md",
                    image_url=None,
                    article_word_count=20,
                    transcript_source="article",
                    warnings=[],
                    tags=[],
                    items=[item],
                )
                with (
                    patch.object(podcast_jobs, "generate_podcast", return_value=generated),
                    patch.object(podcast_jobs, "add_episode"),
                    patch.object(podcast_jobs, "_remember"),
                    patch.dict(os.environ, {}, clear=False),
                ):
                    os.environ.pop("GITHUB_PAGES_URL", None)
                    result = podcast_jobs.run_next()

                self.assertTrue(result["ok"])
                saved = db.get_podcast_job(job_id)
                self.assertEqual(saved["status"], "done")
                self.assertEqual(saved["result"]["title"], "测试播客")
            finally:
                db.DB_PATH = original_path

    def test_publish_failure_keeps_result_retryable(self):
        original_path = db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = str(Path(tmp) / "knowledge.db")
            try:
                db.init_db()
                job_id = db.create_podcast_job("https://example.com", "url", {})
                db.claim_podcast_job(job_id)
                failed_publish = SimpleNamespace(returncode=1, stderr="publish failed", stdout="")
                with (
                    patch.object(podcast_jobs.subprocess, "run", return_value=failed_publish),
                    patch.dict(os.environ, {"GITHUB_PAGES_URL": "https://podcast.example.com"}),
                ):
                    podcast_jobs._publish(job_id, {"title": "已生成"})

                saved = db.get_podcast_job(job_id)
                self.assertEqual(saved["status"], "failed")
                self.assertEqual(saved["stage"], "publishing")
                self.assertEqual(saved["error_code"], "rss_publish_failed")
                self.assertEqual(saved["result"]["title"], "已生成")
            finally:
                db.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
