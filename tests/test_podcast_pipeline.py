from __future__ import annotations

import json
import os
import subprocess
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
from content_to_podcast.generator import normalize_original_audio_for_podcast
from content_to_podcast.source_adapters import (
    BilibiliAdapter,
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

    def test_missing_subtitle_can_skip_whisper_for_original_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / "source.m4a"
            media.write_bytes(b"audio")

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
                    transcribe_missing=False,
                )

            self.assertEqual(prepared.transcript_source, "unavailable")
            self.assertEqual(prepared.text, "")
            self.assertIn("无可用字幕", prepared.warnings[0])
            transcribe.assert_not_called()

    def test_bilibili_original_audio_downloads_audio_and_includes_ai_subtitles(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "BBDown"
            binary.write_text("binary", encoding="utf-8")

            def fake_run(command, **kwargs):
                Path(tmp, "source.m4a").write_bytes(b"audio")
                return SimpleNamespace(stdout="视频标题: 测试标题", stderr="", returncode=0)

            with patch("content_to_podcast.source_adapters._run", side_effect=fake_run) as run:
                prepared = BilibiliAdapter(str(binary)).prepare(
                    "https://b23.tv/test",
                    tmp,
                    use_original_audio=True,
                    transcribe_missing=False,
                )

            command = run.call_args.args[0]
            self.assertIn("--audio-only", command)
            self.assertEqual(command[command.index("--skip-ai") + 1], "false")
            self.assertEqual(prepared.transcript_source, "unavailable")

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
    def test_long_original_audio_is_split_for_static_hosting(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "source.mp3").write_bytes(b"oversized")

            def fake_ffmpeg(command, **kwargs):
                Path(tmp, "source_part000.mp3").write_bytes(b"part-one")
                Path(tmp, "source_part001.mp3").write_bytes(b"part-two")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with (
                patch(
                    "content_to_podcast.generator.normalize_audio_for_podcast",
                    side_effect=RuntimeError("超过 Cloudflare Pages 限制"),
                ),
                patch("content_to_podcast.generator.shutil.which", return_value="/usr/bin/ffmpeg"),
                patch("content_to_podcast.generator.subprocess.run", side_effect=fake_ffmpeg),
            ):
                parts = normalize_original_audio_for_podcast("source.m4a", tmp)

            self.assertEqual(parts, ["source_part000.mp3", "source_part001.mp3"])
            self.assertFalse(Path(tmp, "source.mp3").exists())

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
                prepare_source=lambda source, source_type, callback, force_transcribe, use_original_audio, transcribe_missing: PreparedSource(
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

    def test_original_audio_is_released_before_optional_whisper(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_dir = Path(tmp) / "audio"
            media = Path(tmp) / "source.m4a"
            media.write_bytes(b"audio")
            order = []

            def prepare_source(source, source_type, callback, force_transcribe, use_original_audio, transcribe_missing):
                self.assertTrue(use_original_audio)
                self.assertFalse(transcribe_missing)
                return PreparedSource(
                    source_type="bilibili",
                    original_url=source,
                    canonical_url=source,
                    title="测试标题",
                    text="",
                    transcript_source="unavailable",
                    media_path=str(media),
                    warnings=["无可用字幕。"],
                )

            def transcribe(prepared, callback, force):
                self.assertFalse(force)
                order.append("whisper")
                prepared.text = "Whisper 逐字稿"
                prepared.transcript_source = "whisper"
                return prepared

            services = PodcastGenerationServices(
                extract_content=lambda source, source_type: ("legacy", None),
                download_youtube_audio=lambda source, output_dir: None,
                generate_audio_sync=lambda text, voice, output_dir: "unused.mp3",
                detect_language=lambda text: "zh",
                generate_title=lambda text: "AI 标题",
                format_transcript=lambda text: (order.append("article") or ("知识库文章", ["测试"])),
                distill_and_translate=lambda text: ("摘要", ["测试"]),
                chunk_text=lambda text: [text],
                polish_chunk=lambda text, index, total: text,
                generate_tags=lambda title, text: ["测试"],
                chunk_threshold=1000,
                prepare_source=prepare_source,
                transcribe_prepared_source=transcribe,
            )

            with patch("content_to_podcast.generator.normalize_audio_for_podcast", side_effect=lambda filename, directory: filename):
                result = generate_podcast(
                    PodcastGenerationOptions(
                        source="https://b23.tv/test",
                        source_type="bilibili",
                        use_original_audio=True,
                        whisper_transcribe=True,
                        services=services,
                        audio_dir=str(audio_dir),
                        scripts_dir=str(Path(tmp) / "scripts"),
                        transcripts_dir=str(Path(tmp) / "transcripts"),
                        images_dir=str(Path(tmp) / "images"),
                    ),
                    on_original_audio_ready=lambda items: order.append("audio_published"),
                )

            self.assertEqual(order, ["audio_published", "whisper", "article"])
            self.assertEqual(result.transcript_source, "whisper")
            self.assertTrue(result.article_script_url)

    def test_original_audio_without_subtitle_does_not_run_whisper_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_dir = Path(tmp) / "audio"
            media = Path(tmp) / "source.m4a"
            media.write_bytes(b"audio")
            transcribe = Mock()
            services = PodcastGenerationServices(
                extract_content=lambda source, source_type: ("legacy", None),
                download_youtube_audio=lambda source, output_dir: None,
                generate_audio_sync=lambda text, voice, output_dir: "unused.mp3",
                detect_language=lambda text: "zh",
                generate_title=lambda text: "AI 标题",
                format_transcript=lambda text: ("不应生成", []),
                distill_and_translate=lambda text: ("不应生成", []),
                chunk_text=lambda text: [text],
                polish_chunk=lambda text, index, total: text,
                generate_tags=lambda title, text: [],
                chunk_threshold=1000,
                prepare_source=lambda *args: PreparedSource(
                    source_type="bilibili",
                    original_url=args[0],
                    canonical_url=args[0],
                    title="测试标题",
                    text="",
                    transcript_source="unavailable",
                    media_path=str(media),
                    warnings=["无可用字幕。"],
                ),
                transcribe_prepared_source=transcribe,
            )

            with patch("content_to_podcast.generator.normalize_audio_for_podcast", side_effect=lambda filename, directory: filename):
                result = generate_podcast(PodcastGenerationOptions(
                    source="https://b23.tv/test",
                    source_type="bilibili",
                    use_original_audio=True,
                    services=services,
                    audio_dir=str(audio_dir),
                    scripts_dir=str(Path(tmp) / "scripts"),
                    transcripts_dir=str(Path(tmp) / "transcripts"),
                    images_dir=str(Path(tmp) / "images"),
                ))

            transcribe.assert_not_called()
            self.assertEqual(result.transcript_source, "unavailable")
            self.assertEqual(result.transcript_url, "")
            self.assertEqual(result.article_script_url, "")
            self.assertIn("无可用字幕", result.warnings[0])


class PodcastJobPersistenceTests(unittest.TestCase):
    def test_publisher_timeout_stops_child_process_group(self):
        process = Mock(pid=12345, returncode=-15)
        process.communicate.side_effect = [
            subprocess.TimeoutExpired("publisher", 1),
            ("", ""),
        ]
        with (
            patch.object(podcast_jobs.subprocess, "Popen", return_value=process) as popen,
            patch.object(podcast_jobs.os, "killpg") as killpg,
            self.assertRaises(subprocess.TimeoutExpired),
        ):
            podcast_jobs._run_publisher(1)

        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        killpg.assert_called_once_with(12345, podcast_jobs.signal.SIGTERM)

    def test_isolated_runner_can_import_content_to_podcast_package(self):
        result = subprocess.run(
            [sys.executable, "-m", "services.podcast_job_runner", "missing-job"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

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

    def test_worker_reports_publish_failure_after_generating_content(self):
        original_path = db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = str(Path(tmp) / "knowledge.db")
            try:
                db.init_db()
                job_id = db.create_podcast_job("https://example.com", "url", {})
                item = SimpleNamespace(
                    title="测试播客", description="描述", audio_filename="test.mp3",
                    audio_length=10, image_url=None, audio_mime="audio/mpeg",
                    audio_url="/static/audio/test.mp3", script_url="", transcript_url="",
                    word_count=0,
                )
                generated = SimpleNamespace(
                    title="测试播客", source_url="https://example.com", source_type="url",
                    article_summary="描述", article_script_url="", transcript_url="",
                    image_url=None, article_word_count=0, transcript_source="article",
                    warnings=[], tags=[], items=[item],
                )

                def fail_publish(publishing_job_id, result_payload):
                    db.update_podcast_job(
                        publishing_job_id, status="failed", stage="publishing",
                        error_code="rss_publish_failed", error_message="发布超时",
                        result_json=json.dumps(result_payload),
                    )

                with (
                    patch.object(podcast_jobs, "generate_podcast", return_value=generated),
                    patch.object(podcast_jobs, "add_episode"),
                    patch.object(db, "add_article", return_value="article-id"),
                    patch.object(podcast_jobs, "_publish", side_effect=fail_publish),
                ):
                    result = podcast_jobs.run_next()

                self.assertFalse(result["ok"])
                self.assertEqual(result["error_code"], "rss_publish_failed")
                self.assertEqual(db.get_podcast_job(job_id)["result"]["title"], "测试播客")
            finally:
                db.DB_PATH = original_path

    def test_original_audio_is_added_to_rss_before_background_enrichment(self):
        original_path = db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = str(Path(tmp) / "knowledge.db")
            try:
                db.init_db()
                job_id = db.create_podcast_job(
                    "https://b23.tv/test",
                    "bilibili",
                    {"use_original_audio": True, "whisper_transcribe": True},
                )
                item = SimpleNamespace(
                    title="测试播客",
                    description="无可用字幕或 AI 字幕。",
                    audio_filename="test.mp3",
                    audio_length=10,
                    image_url=None,
                    audio_mime="audio/mpeg",
                    audio_url="http://localhost:8000/static/audio/test.mp3",
                    script_url="/static/scripts/test.md",
                    transcript_url="/static/transcripts/test.md",
                    word_count=20,
                    tags=[],
                    __dict__={"title": "测试播客", "audio_filename": "test.mp3"},
                )
                generated = SimpleNamespace(
                    title="测试播客",
                    source_url="https://b23.tv/test",
                    source_type="bilibili",
                    article_summary="测试描述",
                    article_script_url="/static/scripts/test.md",
                    transcript_url="/static/transcripts/test.md",
                    image_url=None,
                    article_word_count=20,
                    transcript_source="whisper",
                    warnings=[],
                    tags=[],
                    items=[item],
                )
                order = []

                def fake_generate(options, on_status=None, on_original_audio_ready=None):
                    self.assertTrue(options.whisper_transcribe)
                    on_original_audio_ready([item])
                    order.append("whisper_finished")
                    return generated

                with (
                    patch.object(podcast_jobs, "generate_podcast", side_effect=fake_generate),
                    patch.object(podcast_jobs, "add_episode", side_effect=lambda **kwargs: order.append("rss_added")) as add,
                    patch.object(podcast_jobs, "_publish_original_audio", side_effect=lambda *args: order.append("audio_published")),
                    patch.object(podcast_jobs, "_publish"),
                    patch.object(podcast_jobs, "_remember"),
                ):
                    result = podcast_jobs.run_next()

                self.assertTrue(result["ok"])
                self.assertEqual(order, ["rss_added", "audio_published", "whisper_finished"])
                self.assertEqual(add.call_count, 1)
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
                    patch.object(podcast_jobs, "_run_publisher", return_value=failed_publish),
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

    def test_publish_saves_generated_result_before_external_command(self):
        original_path = db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = str(Path(tmp) / "knowledge.db")
            try:
                db.init_db()
                job_id = db.create_podcast_job("https://example.com", "url", {})
                db.claim_podcast_job(job_id)
                result = {"title": "已生成", "items": [{"audio_filename": "episode.mp3"}]}
                observed = {}

                def timed_out(timeout_seconds):
                    observed["result"] = db.get_podcast_job(job_id)["result"]
                    observed["timeout"] = timeout_seconds
                    raise subprocess.TimeoutExpired("publisher", timeout_seconds)

                with (
                    patch.object(podcast_jobs, "_run_publisher", side_effect=timed_out),
                    patch.dict(os.environ, {"GITHUB_PAGES_URL": "https://podcast.example.com"}),
                ):
                    podcast_jobs._publish(job_id, result)

                saved = db.get_podcast_job(job_id)
                self.assertEqual(observed["result"]["title"], "已生成")
                self.assertLess(observed["timeout"], podcast_jobs._stage_timeout_seconds("publishing"))
                self.assertEqual(saved["error_code"], "rss_publish_failed")
                self.assertEqual(saved["result"]["items"][0]["audio_filename"], "episode.mp3")
            finally:
                db.DB_PATH = original_path

    def test_publishing_watchdog_preserves_saved_result_for_retry(self):
        original_path = db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = str(Path(tmp) / "knowledge.db")
            try:
                db.init_db()
                job_id = db.create_podcast_job("https://example.com", "url", {})
                db.claim_podcast_job(job_id)
                db.update_podcast_job(
                    job_id,
                    stage="publishing",
                    result_json=json.dumps({"title": "已生成"}),
                )

                podcast_jobs._mark_timed_out(job_id, "publishing", 900)

                saved = db.get_podcast_job(job_id)
                self.assertEqual(saved["error_code"], "rss_publish_failed")
                self.assertEqual(saved["result"]["title"], "已生成")
            finally:
                db.DB_PATH = original_path

    def test_job_management_tracks_queue_cancel_retry_and_events(self):
        original_path = db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = str(Path(tmp) / "knowledge.db")
            try:
                db.init_db()
                first = db.create_podcast_job("https://example.com/one", "url", {"title": "one"})
                second = db.create_podcast_job("https://example.com/two", "url", {"title": "two"})

                listed = {job["id"]: job for job in db.list_podcast_jobs()}
                self.assertEqual(listed[first]["queue_position"], 1)
                self.assertEqual(listed[second]["queue_position"], 2)

                self.assertTrue(db.request_podcast_job_cancel(first))
                self.assertEqual(db.get_podcast_job(first)["status"], "cancelled")
                self.assertEqual(db.list_podcast_jobs(status="pending")[0]["queue_position"], 1)
                self.assertEqual(db.get_podcast_job_events(first)[-1]["event_type"], "cancelled")

                retried = db.retry_podcast_job(first)
                retry_job = db.get_podcast_job(retried)
                self.assertEqual(retry_job["parent_job_id"], first)
                self.assertEqual(retry_job["attempt_count"], 2)
            finally:
                db.DB_PATH = original_path

    def test_restart_recovers_running_but_finishes_cancelling(self):
        original_path = db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = str(Path(tmp) / "knowledge.db")
            try:
                db.init_db()
                running = db.create_podcast_job("https://example.com/running", "url", {})
                cancelling = db.create_podcast_job("https://example.com/cancelling", "url", {})
                db.claim_podcast_job(running)
                db.claim_podcast_job(cancelling)
                db.request_podcast_job_cancel(cancelling)

                self.assertEqual(db.reset_running_podcast_jobs(), 1)
                self.assertEqual(db.get_podcast_job(running)["status"], "pending")
                self.assertEqual(db.get_podcast_job(cancelling)["status"], "cancelled")
            finally:
                db.DB_PATH = original_path

    def test_isolated_worker_terminates_cancelled_job(self):
        original_path = db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = str(Path(tmp) / "knowledge.db")
            try:
                db.init_db()
                job_id = db.create_podcast_job("https://example.com", "url", {})
                db.claim_podcast_job(job_id)
                db.request_podcast_job_cancel(job_id)
                process = Mock()
                process.poll.side_effect = lambda: process.returncode
                process.returncode = None

                def terminate():
                    process.returncode = -15

                process.terminate.side_effect = terminate
                with (
                    patch.object(podcast_jobs.subprocess, "Popen", return_value=process),
                    patch.object(podcast_jobs._stop_event, "wait", return_value=False),
                ):
                    result = podcast_jobs._run_isolated(job_id)

                self.assertEqual(result["error_code"], "cancelled")
                self.assertEqual(db.get_podcast_job(job_id)["status"], "cancelled")
                process.terminate.assert_called_once()
            finally:
                podcast_jobs._active_process = None
                podcast_jobs._active_job_id = None
                db.DB_PATH = original_path

    def test_isolated_worker_marks_process_start_failure(self):
        original_path = db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = str(Path(tmp) / "knowledge.db")
            try:
                db.init_db()
                job_id = db.create_podcast_job("https://example.com", "url", {})
                db.claim_podcast_job(job_id)
                with patch.object(
                    podcast_jobs.subprocess,
                    "Popen",
                    side_effect=OSError("cannot spawn"),
                ):
                    result = podcast_jobs._run_isolated(job_id)

                self.assertEqual(result["error_code"], "worker_start_failed")
                saved = db.get_podcast_job(job_id)
                self.assertEqual(saved["status"], "failed")
                self.assertEqual(saved["error_code"], "worker_start_failed")
            finally:
                podcast_jobs._active_process = None
                podcast_jobs._active_job_id = None
                db.DB_PATH = original_path

    def test_isolated_worker_terminates_timed_out_job(self):
        original_path = db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = str(Path(tmp) / "knowledge.db")
            try:
                db.init_db()
                job_id = db.create_podcast_job("https://example.com", "url", {})
                db.claim_podcast_job(job_id)
                process = Mock()
                process.poll.side_effect = lambda: process.returncode
                process.returncode = None

                def terminate():
                    process.returncode = -15

                process.terminate.side_effect = terminate
                with (
                    patch.object(podcast_jobs.subprocess, "Popen", return_value=process),
                    patch.object(podcast_jobs._stop_event, "wait", return_value=False),
                    patch.object(podcast_jobs, "_seconds_since", return_value=999),
                    patch.object(podcast_jobs, "_stage_timeout_seconds", return_value=1),
                ):
                    result = podcast_jobs._run_isolated(job_id)

                self.assertEqual(result["error_code"], "stage_timeout")
                saved = db.get_podcast_job(job_id)
                self.assertEqual(saved["status"], "failed")
                self.assertEqual(saved["error_code"], "stage_timeout")
                process.terminate.assert_called_once()
            finally:
                podcast_jobs._active_process = None
                podcast_jobs._active_job_id = None
                db.DB_PATH = original_path


if __name__ == "__main__":
    unittest.main()
