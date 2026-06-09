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
_active_process: subprocess.Popen | None = None
_active_job_id: str | None = None

STAGE_MAP = {
    "extracting": "resolving",
    "resolving": "resolving",
    "downloading": "downloading",
    "transcribing": "transcribing",
    "processing": "writing_script",
    "generating_audio": "generating_audio",
    "publishing": "publishing",
}

DEFAULT_STAGE_TIMEOUTS = {
    "resolving": 3 * 60,
    "downloading": 30 * 60,
    "transcribing": 90 * 60,
    "writing_script": 30 * 60,
    "generating_audio": 30 * 60,
    "publishing": 15 * 60,
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
    _terminate_active_process()
    if _worker_thread and _worker_thread.is_alive():
        _worker_thread.join(timeout=5)


def enqueue(source_url: str, source_type: str, options: dict) -> str:
    return db.create_podcast_job(source_url, source_type, options)


def cancel(job_id: str) -> dict:
    if not db.request_podcast_job_cancel(job_id):
        return {"ok": False, "error": "任务不存在、已结束或无法取消"}
    return {"ok": True, "job": db.get_podcast_job(job_id)}


def retry(job_id: str) -> dict:
    new_job_id = db.retry_podcast_job(job_id)
    if not new_job_id:
        return {"ok": False, "error": "只有失败或已取消的任务可以重试"}
    return {"ok": True, "job_id": new_job_id, "job": db.get_podcast_job(new_job_id)}


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
            job = db.get_next_podcast_job()
            if job and db.claim_podcast_job(job["id"]):
                _run_isolated(job["id"])
            else:
                _stop_event.wait(1)
        except Exception:
            log.exception("podcast worker loop failed")
            _stop_event.wait(2)


def _run_isolated(job_id: str) -> dict:
    global _active_process, _active_job_id
    _active_job_id = job_id
    try:
        _active_process = subprocess.Popen(
            [sys.executable, "-m", "services.podcast_job_runner", job_id],
            cwd=os.getcwd(),
        )
    except Exception as exc:
        message = f"无法启动任务子进程：{exc}"
        db.update_podcast_job(
            job_id,
            status="failed",
            stage="failed",
            message=message,
            error_code="worker_start_failed",
            error_message=message,
            finished_at=_now(),
        )
        db.add_podcast_job_event(job_id, "failed", "failed", message)
        _active_job_id = None
        return {"ok": False, "job_id": job_id, "error_code": "worker_start_failed"}
    try:
        while _active_process.poll() is None:
            if _stop_event.wait(1):
                _terminate_active_process()
                return {"ok": False, "job_id": job_id, "error": "worker stopped"}
            job = db.get_podcast_job(job_id)
            if not job:
                _terminate_active_process()
                return {"ok": False, "job_id": job_id, "error": "job deleted"}
            if job["status"] == "cancelling":
                _terminate_active_process()
                _mark_cancelled(job_id)
                return {"ok": False, "job_id": job_id, "error_code": "cancelled"}
            timeout_seconds = _stage_timeout_seconds(job.get("stage") or "resolving")
            elapsed = _seconds_since(job.get("updated_at"))
            if timeout_seconds and elapsed > timeout_seconds:
                _terminate_active_process()
                _mark_timed_out(job_id, job.get("stage") or "unknown", timeout_seconds)
                return {"ok": False, "job_id": job_id, "error_code": "stage_timeout"}

        job = db.get_podcast_job(job_id)
        if _active_process.returncode and job and job["status"] == "running":
            message = f"任务子进程异常退出，退出码 {_active_process.returncode}。"
            db.update_podcast_job(
                job_id,
                status="failed",
                stage="failed",
                message=message,
                error_code="worker_process_failed",
                error_message=message,
                finished_at=_now(),
            )
            db.add_podcast_job_event(job_id, "failed", "failed", message)
        return {"ok": bool(job and job["status"] == "done"), "job_id": job_id}
    finally:
        _active_process = None
        _active_job_id = None


def _terminate_active_process() -> None:
    global _active_process
    process = _active_process
    if not process or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _stage_timeout_seconds(stage: str) -> int:
    env_name = f"PODCAST_TIMEOUT_{stage.upper()}_SECONDS"
    try:
        return max(0, int(os.getenv(env_name, DEFAULT_STAGE_TIMEOUTS.get(stage, 30 * 60))))
    except ValueError:
        log.warning("invalid %s; using default timeout", env_name)
        return DEFAULT_STAGE_TIMEOUTS.get(stage, 30 * 60)


def _seconds_since(timestamp: str | None) -> float:
    if not timestamp:
        return 0
    try:
        value = datetime.fromisoformat(timestamp)
        return max(0, (datetime.now(timezone.utc) - value).total_seconds())
    except Exception:
        return 0


def _mark_cancelled(job_id: str) -> None:
    db.update_podcast_job(
        job_id,
        status="cancelled",
        stage="cancelled",
        message="任务已取消。",
        error_code="cancelled",
        error_message="任务由用户取消。",
        finished_at=_now(),
    )
    db.add_podcast_job_event(job_id, "cancelled", "cancelled", "任务已取消。")
    _sync_inbox_status(job_id, "pending")


def _mark_timed_out(job_id: str, stage: str, timeout_seconds: int) -> None:
    message = f"任务在 {stage} 阶段超过 {timeout_seconds // 60} 分钟，已自动终止。"
    db.update_podcast_job(
        job_id,
        status="failed",
        stage=stage,
        message=message,
        error_code="stage_timeout",
        error_message=message,
        timeout_at=_now(),
        finished_at=_now(),
    )
    db.add_podcast_job_event(job_id, "timeout", stage, message)
    _sync_inbox_status(job_id, "pending")


def _run(job_id: str) -> dict:
    job = db.get_podcast_job(job_id)
    if not job:
        return {"ok": False, "error": "job not found"}
    options = job.get("options") or {}

    def on_status(status: str, message: str, file: dict | None = None):
        previous = db.get_podcast_job(job_id)
        stage = STAGE_MAP.get(status, status)
        db.update_podcast_job(
            job_id,
            stage=stage,
            message=message,
            heartbeat_at=_now(),
        )
        if not previous or previous.get("stage") != stage or previous.get("message") != message:
            db.add_podcast_job_event(job_id, "progress", stage, message)
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
        _sync_inbox_status(job_id, "done")
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
        db.add_podcast_job_event(job_id, "failed", "failed", str(exc), {"error_code": error_code})
        _sync_inbox_status(job_id, "pending")
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
        db.add_podcast_job_event(job_id, "completed", "done", "内容生成完成。")
        return

    db.update_podcast_job(
        job_id,
        stage="publishing",
        message="内容生成完成，正在发布到 RSS...",
        heartbeat_at=_now(),
    )
    db.add_podcast_job_event(job_id, "progress", "publishing", "内容生成完成，正在发布到 RSS...")
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
        db.add_podcast_job_event(job_id, "completed", "done", "全部完成，已发布到 RSS。")
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
        db.add_podcast_job_event(job_id, "failed", "publishing", str(exc), {"error_code": "rss_publish_failed"})


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


def _sync_inbox_status(job_id: str, status: str) -> None:
    job = db.get_podcast_job(job_id)
    inbox_item_id = (job.get("options") or {}).get("inbox_item_id") if job else None
    if inbox_item_id:
        db.update_inbox_item(inbox_item_id, status=status)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
