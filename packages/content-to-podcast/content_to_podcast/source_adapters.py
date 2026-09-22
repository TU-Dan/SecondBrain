from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

from .transcription import transcribe_audio


MIN_TRANSCRIPT_CHARS = 200
URL_PATTERN = re.compile(r"https?://[^\s]+", re.I)


class SourcePreparationError(RuntimeError):
    def __init__(self, message: str, error_code: str = "platform_download_failed"):
        super().__init__(message)
        self.error_code = error_code


@dataclass
class PreparedSource:
    source_type: str
    original_url: str
    canonical_url: str
    title: str
    text: str
    transcript_source: str
    thumbnail_url: str | None = None
    media_path: str | None = None
    warnings: list[str] = field(default_factory=list)
    transcript_files: list[str] = field(default_factory=list)
    work_dir: str | None = None


def _notify(callback: Callable | None, stage: str, message: str) -> None:
    if callback:
        callback(stage, message, None)


def _run(command: list[str], timeout: int = 1800, cwd: str | None = None) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SourcePreparationError(f"外部下载工具运行超时：{' '.join(command[:2])}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-1200:]
        code = "cookie_required" if re.search(r"cookie|登录|扫码|风控|验证", detail, re.I) else "platform_download_failed"
        raise SourcePreparationError(f"外部下载工具失败：{detail}", code)
    return result


def _extract_audio(media_path: str, output_dir: str) -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SourcePreparationError("未找到 ffmpeg，无法从视频中提取音频。")
    output_path = str(Path(output_dir) / f"{Path(media_path).stem}.wav")
    _run([ffmpeg, "-y", "-i", media_path, "-vn", "-ac", "1", "-ar", "16000", output_path])
    return output_path


def _find_media(directory: str) -> str | None:
    extensions = {".mp4", ".mkv", ".webm", ".mov", ".m4a", ".mp3", ".aac", ".flac", ".wav"}
    candidates = [
        path for path in Path(directory).rglob("*")
        if path.is_file() and path.suffix.lower() in extensions
    ]
    return str(max(candidates, key=lambda p: p.stat().st_size)) if candidates else None


def _subtitle_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".ass":
        dialogue = []
        for line in raw.splitlines():
            if line.startswith("Dialogue:"):
                fields = line.split(",", 9)
                if len(fields) == 10:
                    dialogue.append(fields[-1])
        raw = "\n".join(dialogue)
    raw = re.sub(r"(?m)^\d+\s*$", "", raw)
    raw = re.sub(r"\d{1,2}:\d{2}:\d{2}[,\.]\d+\s+-->\s+\d{1,2}:\d{2}:\d{2}[,\.]\d+", "", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def _find_subtitle(directory: str) -> tuple[str, str] | None:
    candidates = [
        path for path in Path(directory).rglob("*")
        if path.is_file() and path.suffix.lower() in {".srt", ".vtt", ".ass"}
    ]
    for path in candidates:
        text = _subtitle_text(path)
        if len(text) >= MIN_TRANSCRIPT_CHARS:
            return text, str(path)
    return None


def _find_cached_whisper(media_path: str) -> tuple[str, list[str]] | None:
    media = Path(media_path)
    markdown = media.with_name(f"{media.stem}_whisper.md")
    srt = media.with_suffix(".srt")
    if not markdown.is_file():
        return None
    text = markdown.read_text(encoding="utf-8", errors="replace")
    text = text.split("---", 1)[-1].strip()
    if len(text) < MIN_TRANSCRIPT_CHARS:
        return None
    files = [str(markdown)]
    if srt.is_file():
        files.insert(0, str(srt))
    return text, files


def _metadata_from_files(directory: str) -> dict:
    for path in Path(directory).rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


def _recursive_value(data, keys: set[str]):
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in keys and value:
                return value
        for value in data.values():
            found = _recursive_value(value, keys)
            if found:
                return found
    elif isinstance(data, list):
        for value in data:
            found = _recursive_value(value, keys)
            if found:
                return found
    return None


def _download_url(url: str, output_dir: str) -> str:
    suffix = Path(urlparse(url).path).suffix or ".mp4"
    target = Path(output_dir) / f"source{suffix}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as response, target.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    return str(target)


def _extract_shared_url(value: str, hosts: tuple[str, ...]) -> str:
    for match in URL_PATTERN.finditer(value.strip()):
        url = match.group(0).rstrip(".,;:!?，。；：！？、）)]}>")
        if any(host in url.lower() for host in hosts):
            return url
    return value.strip()


class DouyinAdapter:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv("DOUYIN_DOWNLOADER_BASE_URL", "http://127.0.0.1:18080")).rstrip("/")

    def prepare(
        self,
        url: str,
        work_dir: str,
        on_status: Callable | None = None,
        force_transcribe: bool = False,
        use_original_audio: bool = False,
        transcribe_missing: bool = True,
    ) -> PreparedSource:
        resolved_url = _extract_shared_url(url, ("douyin.com", "iesdouyin.com"))
        _notify(on_status, "resolving", "正在通过抖音专用下载器解析作品...")
        started_at = time.time()
        download_dir = os.getenv("DOUYIN_DOWNLOAD_DIR", "tools/douyin-downloader/Downloaded")
        existing_media = {str(path) for path in _media_files(download_dir)}
        data = self._submit(resolved_url)

        task_id = _recursive_value(data, {"task_id", "taskid", "job_id", "jobid", "id"})
        if task_id and not _recursive_value(data, {"download_url", "video_url", "play_url", "file_path", "path"}):
            data = self._poll_task(str(task_id))

        media_value = _recursive_value(data, {"download_url", "video_url", "play_url", "file_path", "path"})
        if not media_value:
            media_value = _find_recent_media(download_dir, started_at, existing_media)
        if not media_value:
            raise SourcePreparationError(
                "抖音下载器未返回视频文件。短链可能已过期或作品需要 Cookie。",
                "expired_share_link" if "v.douyin.com" in resolved_url else "platform_download_failed",
            )

        _notify(on_status, "downloading", "正在下载抖音完整视频...")
        media_path = str(media_value)
        if media_path.startswith("http"):
            media_path = _download_url(media_path, work_dir)
        if not os.path.exists(media_path):
            raise SourcePreparationError("抖音下载器返回的视频文件不存在。")
        media_metadata = _metadata_from_files(str(Path(media_path).parent))

        return _finish_video_source(
            source_type="douyin",
            original_url=url,
            canonical_url=str(
                _recursive_value(media_metadata, {"share_url"})
                or _recursive_value(data, {"canonical_url", "share_url", "url"})
                or resolved_url
            ),
            title=str(
                _recursive_value(media_metadata, {"title", "desc", "description"})
                or _recursive_value(data, {"title", "desc", "description"})
                or "抖音视频"
            ),
            thumbnail_url=_recursive_value(data, {"cover", "cover_url", "thumbnail", "thumbnail_url"}),
            media_path=media_path,
            work_dir=work_dir,
            on_status=on_status,
            force_transcribe=force_transcribe,
            transcribe_missing=transcribe_missing,
        )

    def _submit(self, url: str) -> dict:
        errors: list[str] = []
        validation_error = False
        for body in ({"url": url}, {"urls": [url]}):
            request = urllib.request.Request(
                f"{self.base_url}/api/v1/download",
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                errors.append(exc.read().decode("utf-8", errors="replace")[:500])
                validation_error = validation_error or exc.code in {400, 404, 422}
                if exc.code not in {400, 422}:
                    break
            except Exception as exc:
                errors.append(str(exc))
                break
        detail = " | ".join(error for error in errors if error)
        raise SourcePreparationError(
            "无法调用抖音专用下载器。请确认服务已启动，且链接为公开有效作品。"
            + (f" 详情：{detail}" if detail else ""),
            "expired_share_link" if validation_error and "v.douyin.com" in url else "platform_download_failed",
        )

    def _poll_task(self, task_id: str) -> dict:
        candidates = [
            f"{self.base_url}/api/v1/jobs/{task_id}",
            f"{self.base_url}/api/v1/download/{task_id}",
            f"{self.base_url}/api/v1/status/{task_id}",
        ]
        last_data: dict = {}
        for _ in range(120):
            for endpoint in candidates:
                try:
                    with urllib.request.urlopen(endpoint, timeout=10) as response:
                        last_data = json.loads(response.read().decode("utf-8"))
                    status = str(_recursive_value(last_data, {"status", "state"}) or "").lower()
                    if status in {"failed", "error"}:
                        detail = str(_recursive_value(last_data, {"error", "message"}) or "").strip()
                        if not detail and int(_recursive_value(last_data, {"failed"}) or 0) > 0:
                            raise SourcePreparationError(
                                "抖音无法获取作品详情，通常是触发反爬验证或 Cookie 已失效。"
                                "请运行 bash scripts/capture_douyin_cookie.sh，"
                                "登录抖音后重启下载服务。",
                                "cookie_required",
                            )
                        raise SourcePreparationError(
                            detail or "抖音下载任务失败",
                            "cookie_required"
                            if re.search(r"cookie|登录|验证|anti.?bot|empty 200", detail, re.I)
                            else "platform_download_failed",
                        )
                    if status in {"done", "completed", "success", "succeeded"}:
                        return last_data
                    if _recursive_value(last_data, {"download_url", "video_url", "play_url", "file_path", "path"}):
                        return last_data
                except SourcePreparationError:
                    raise
                except Exception:
                    continue
            time.sleep(2)
        raise SourcePreparationError("抖音下载任务等待超时。")


def _media_files(directory: str) -> list[Path]:
    if not os.path.isdir(directory):
        return []
    extensions = {".mp4", ".mkv", ".webm", ".mov"}
    return [
        path for path in Path(directory).rglob("*")
        if path.is_file()
        and path.suffix.lower() in extensions
    ]


def _find_recent_media(directory: str, started_at: float, existing_media: set[str]) -> str | None:
    all_media = _media_files(directory)
    new_media = [path for path in all_media if str(path) not in existing_media]
    candidates = new_media or [path for path in all_media if path.stat().st_mtime >= started_at - 5]
    if not candidates and all_media:
        candidates = all_media
    return str(max(candidates, key=lambda path: path.stat().st_mtime)) if candidates else None


class BilibiliAdapter:
    def __init__(self, binary_path: str | None = None):
        self.binary_path = binary_path or os.getenv("BBDOWN_PATH", "tools/BBDown/BBDown")

    def prepare(
        self,
        url: str,
        work_dir: str,
        on_status: Callable | None = None,
        force_transcribe: bool = False,
        use_original_audio: bool = False,
        transcribe_missing: bool = True,
    ) -> PreparedSource:
        if not os.path.exists(self.binary_path):
            raise SourcePreparationError(
                "未安装 BBDown。请先运行 scripts/setup_podcast_tools_macos.sh。"
            )
        _notify(on_status, "downloading", "正在通过 BBDown 获取 B站字幕和媒体...")
        command = [
            self.binary_path,
            url,
            "--work-dir", work_dir,
            "--file-pattern", "source",
            "--multi-file-pattern", "source",
            "--skip-ai", "false",
        ]
        if use_original_audio:
            command.append("--audio-only")
        cookie_file = os.getenv("BILIBILI_COOKIE_FILE", "data/cookies/bilibili.txt")
        if os.path.exists(cookie_file):
            cookie = Path(cookie_file).read_text(encoding="utf-8").strip()
            if cookie:
                command.extend(["--cookie", cookie])
        result = _run(command)
        media_path = _find_media(work_dir)
        if not media_path:
            raise SourcePreparationError("BBDown 未生成可用媒体文件。")
        metadata = _metadata_from_files(work_dir)
        title = str(_recursive_value(metadata, {"title"}) or _title_from_output(result.stdout) or "B站视频")
        return _finish_video_source(
            source_type="bilibili",
            original_url=url,
            canonical_url=url,
            title=title,
            thumbnail_url=_recursive_value(metadata, {"cover", "pic", "thumbnail"}),
            media_path=media_path,
            work_dir=work_dir,
            on_status=on_status,
            force_transcribe=force_transcribe,
            transcribe_missing=transcribe_missing,
        )


def _title_from_output(output: str) -> str:
    for line in output.splitlines():
        match = re.search(r"(?:标题|Title)\s*[:：]\s*(.+)", line, re.I)
        if match:
            return match.group(1).strip()
    return ""


def _finish_video_source(
    *,
    source_type: str,
    original_url: str,
    canonical_url: str,
    title: str,
    thumbnail_url: str | None,
    media_path: str,
    work_dir: str,
    on_status: Callable | None,
    force_transcribe: bool = False,
    transcribe_missing: bool = True,
) -> PreparedSource:
    subtitle = _find_subtitle(work_dir)
    if subtitle and not force_transcribe:
        text, subtitle_path = subtitle
        return PreparedSource(
            source_type=source_type,
            original_url=original_url,
            canonical_url=canonical_url,
            title=title,
            text=text,
            transcript_source="platform_subtitle",
            thumbnail_url=thumbnail_url,
            media_path=media_path,
            transcript_files=[subtitle_path],
            work_dir=work_dir,
        )

    cached_whisper = _find_cached_whisper(media_path)
    if cached_whisper and not force_transcribe and transcribe_missing:
        text, transcript_files = cached_whisper
        return PreparedSource(
            source_type=source_type,
            original_url=original_url,
            canonical_url=canonical_url,
            title=title,
            text=text,
            transcript_source="whisper",
            thumbnail_url=thumbnail_url,
            media_path=media_path,
            transcript_files=transcript_files,
            work_dir=work_dir,
        )

    if not transcribe_missing:
        return PreparedSource(
            source_type=source_type,
            original_url=original_url,
            canonical_url=canonical_url,
            title=title,
            text="",
            transcript_source="unavailable",
            thumbnail_url=thumbnail_url,
            media_path=media_path,
            warnings=["无可用字幕或 AI 字幕。"],
            work_dir=work_dir,
        )

    prepared = PreparedSource(
        source_type=source_type,
        original_url=original_url,
        canonical_url=canonical_url,
        title=title,
        text="",
        transcript_source="unavailable",
        thumbnail_url=thumbnail_url,
        media_path=media_path,
        work_dir=work_dir,
    )
    return transcribe_prepared_source(prepared, on_status, force=force_transcribe)


def transcribe_prepared_source(
    prepared: PreparedSource,
    on_status: Callable | None = None,
    force: bool = False,
) -> PreparedSource:
    if not prepared.media_path:
        raise SourcePreparationError("没有可供 Whisper 转录的音频。", "transcription_failed")

    cached_whisper = _find_cached_whisper(prepared.media_path)
    if cached_whisper and not force:
        text, transcript_files = cached_whisper
        return replace(
            prepared,
            text=text,
            transcript_source="whisper",
            transcript_files=transcript_files,
            warnings=[warning for warning in prepared.warnings if "无可用字幕" not in warning],
        )

    message = (
        "正在按要求使用 Faster-Whisper 重新转录..."
        if force
        else "原始音频已发布；没有可用平台字幕，正在后台使用 Faster-Whisper 转录..."
    )
    _notify(on_status, "transcribing", message)
    media_path = prepared.media_path
    work_dir = prepared.work_dir or str(Path(media_path).parent)
    audio_path = media_path if Path(media_path).suffix.lower() in {".mp3", ".m4a", ".aac", ".flac", ".wav"} else _extract_audio(media_path, work_dir)
    transcription = transcribe_audio(audio_path, work_dir)
    media = Path(media_path)
    cache_srt = media.with_suffix(".srt")
    cache_markdown = media.with_name(f"{media.stem}_whisper.md")
    if Path(transcription.srt_path).is_file() and Path(transcription.srt_path) != cache_srt:
        shutil.copy2(transcription.srt_path, cache_srt)
    if Path(transcription.markdown_path).is_file() and Path(transcription.markdown_path) != cache_markdown:
        shutil.copy2(transcription.markdown_path, cache_markdown)
    return replace(
        prepared,
        text=transcription.text,
        transcript_source="whisper",
        media_path=audio_path,
        transcript_files=[
            str(path)
            for path in (cache_srt, cache_markdown)
            if path.is_file()
        ] or [transcription.srt_path, transcription.markdown_path],
        warnings=[warning for warning in prepared.warnings if "无可用字幕" not in warning],
        work_dir=work_dir,
    )


def create_work_dir(source_type: str) -> str:
    path = Path(os.getenv("PODCAST_MEDIA_DIR", "data/podcast_media")) / f"{source_type}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)
