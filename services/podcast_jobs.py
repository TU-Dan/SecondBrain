from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

from content_to_podcast import PodcastGenerationOptions, generate_podcast
from services import db, memory
from services.rss import add_episode

log = logging.getLogger("podcast_jobs")

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()

STAGE_MAP = {
    "extracting": "resolving",
    "resolving": "resolving",
    "downloading": "downloading",
    "transcribing": "transcribing",
    "processing": "writing_script",
    "generating_audio": "generating_audio",
    "publishing": "publishing",
}


def start() -> None:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    configured_concurrency = int(os.getenv("PODCAST_WORKER_CONCURRENCY", "1"))
    if configured_concurrency != 1:
        log.warning(
            "PODCAST_WORKER_CONCURRENCY=%s is not supported yet; using one worker",
            configured_concurrency,
        )
    recovered = db.reset_running_podcast_jobs()
    if recovered:
        log.info("recovered %s interrupted podcast job(s)", recovered)
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="podcast-worker")
    _worker_thread.start()


def stop() -> None:
    _stop_event.set()
    if _worker_thread and _worker_thread.is_alive():
        _worker_thread.join(timeout=5)


def enqueue(source_url: str, source_type: str, options: dict) -> str:
    return db.create_podcast_job(source_url, source_type, options)


def run_next() -> dict | None:
    job = db.get_next_podcast_job()
    if not job or not db.claim_podcast_job(job["id"]):
        return None
    return _run(job["id"])


def retry_publish(job_id: str) -> dict:
    job = db.get_podcast_job(job_id)
    if not job:
        return {"ok": False, "error": "job not found"}
    result = job.get("result") or {}
    if not result:
        return {"ok": False, "error": "任务还没有可发布的生成结果"}
    db.update_podcast_job(job_id, error_code=None, error_message=None)
    _publish(job_id, result)
    updated = db.get_podcast_job(job_id)
    return {
        "ok": updated.get("error_code") != "rss_publish_failed",
        "job": updated,
    }


def _worker_loop() -> None:
    while not _stop_event.is_set():
        try:
            result = run_next()
            if not result:
                _stop_event.wait(1)
        except Exception:
            log.exception("podcast worker loop failed")
            _stop_event.wait(2)


def _run(job_id: str) -> dict:
    job = db.get_podcast_job(job_id)
    if not job:
        return {"ok": False, "error": "job not found"}
    options = job.get("options") or {}

    def on_status(status: str, message: str, file: dict | None = None):
        db.update_podcast_job(
            job_id,
            stage=STAGE_MAP.get(status, status),
            message=message,
        )
        if file:
            db.append_podcast_job_file(job_id, file)

    try:
        result = generate_podcast(
            PodcastGenerationOptions(
                source=job["source_url"],
                source_type=job["source_type"],
                title=options.get("title", ""),
                base_url=options.get("base_url", "http://localhost:8000"),
                voice=options.get("voice", "zh-CN-YunxiNeural"),
                use_original_audio=bool(options.get("use_original_audio")),
                summarize=bool(options.get("summarize")),
                force_transcribe=bool(options.get("force_transcribe")),
            ),
            on_status=on_status,
        )

        for item in result.items:
            add_episode(
                title=item.title,
                description=item.description,
                audio_filename=item.audio_filename,
                audio_length=item.audio_length,
                base_url=options.get("base_url", "http://localhost:8000"),
                episode_image=item.image_url,
                audio_mime=item.audio_mime,
            )

        primary = result.items[0]
        article_id = db.add_article(
            title=result.title,
            source_url=result.source_url,
            source_type=result.source_type,
            summary=result.article_summary or primary.description,
            article_md_path=result.article_script_url or primary.script_url,
            transcript_path=result.transcript_url,
            audio_url=primary.audio_url,
            audio_length=primary.audio_length,
            image_url=result.image_url or primary.image_url,
            word_count=result.article_word_count or primary.word_count,
        )
        if result.tags:
            db.update_tags(article_id, result.tags)
        threading.Thread(target=_remember, args=(article_id,), daemon=True).start()

        result_payload = {
            "title": result.title,
            "article_id": article_id,
            "transcript_source": result.transcript_source,
            "warnings": result.warnings,
            "items": [item.__dict__ for item in result.items],
        }
        _publish(job_id, result_payload)
        return {"ok": True, "job_id": job_id, "result": result_payload}
    except Exception as exc:
        error_code = getattr(exc, "error_code", None) or _infer_error_code(str(exc))
        db.update_podcast_job(
            job_id,
            status="failed",
            stage="failed",
            message=f"处理出错：{exc}",
            error_code=error_code,
            error_message=str(exc),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        log.exception("podcast job failed: %s", job_id)
        return {"ok": False, "job_id": job_id, "error_code": error_code, "error": str(exc)}
    finally:
        if job["source_type"] in {"pdf", "txt"} and os.path.exists(job["source_url"]):
            try:
                os.remove(job["source_url"])
            except OSError:
                pass


def _publish(job_id: str, result_payload: dict) -> None:
    result_payload.pop("publish_error", None)
    pages_url = os.getenv("GITHUB_PAGES_URL", "").rstrip("/")
    if not pages_url:
        db.update_podcast_job(
            job_id,
            status="done",
            stage="done",
            message="内容生成完成；未配置远程 RSS 发布地址。",
            result_json=json.dumps(result_payload, ensure_ascii=False),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        return

    db.update_podcast_job(job_id, stage="publishing", message="内容生成完成，正在发布到 RSS...")
    try:
        publish = subprocess.run(
            [sys.executable, "scripts/publish_to_pages.py"],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if publish.returncode != 0:
            raise RuntimeError((publish.stderr or publish.stdout or "未知发布错误").strip())
        result_payload["rss_url"] = f"{pages_url}/podcast.xml"
        db.update_podcast_job(
            job_id,
            status="done",
            stage="done",
            message="全部完成，已发布到 RSS。",
            result_json=json.dumps(result_payload, ensure_ascii=False),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        result_payload["publish_error"] = str(exc)
        db.update_podcast_job(
            job_id,
            status="failed",
            stage="publishing",
            message=f"内容已生成，但 RSS 发布失败：{exc}",
            result_json=json.dumps(result_payload, ensure_ascii=False),
            error_code="rss_publish_failed",
            error_message=str(exc),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )


def _remember(article_id: str) -> None:
    try:
        article = db.get_article(article_id)
        if article:
            memory.remember(article)
    except Exception:
        log.exception("failed to remember podcast article: %s", article_id)


def _infer_error_code(message: str) -> str:
    lower = message.lower()
    if "短链" in message or "过期" in message:
        return "expired_share_link"
    if "cookie" in lower or "登录" in message or "验证" in message:
        return "cookie_required"
    if "whisper" in lower or "转录" in message:
        return "transcription_failed"
    if "字幕" in message:
        return "subtitle_unavailable"
    return "platform_download_failed"
