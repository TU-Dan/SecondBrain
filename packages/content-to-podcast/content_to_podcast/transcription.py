from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_HF_ENDPOINT = os.getenv("WHISPER_HF_ENDPOINT", "https://hf-mirror.com").strip()
if _DEFAULT_HF_ENDPOINT and not os.getenv("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = _DEFAULT_HF_ENDPOINT

_MODEL_CACHE: dict[tuple[str, str, str, str], object] = {}


class TranscriptionError(RuntimeError):
    error_code = "transcription_failed"


@dataclass
class TranscriptionResult:
    text: str
    language: str
    srt_path: str
    markdown_path: str


def _srt_timestamp(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1_000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def transcribe_audio(audio_path: str, output_dir: str) -> TranscriptionResult:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptionError(
            "未安装 faster-whisper。请先运行 scripts/setup_podcast_tools_macos.sh。"
        ) from exc

    model_name = os.getenv("WHISPER_MODEL", "small")
    local_model_dir = Path(
        os.getenv("WHISPER_LOCAL_MODEL_DIR", f"data/models/faster-whisper-{model_name}-local")
    )
    model_source = str(local_model_dir) if (local_model_dir / "model.bin").is_file() else model_name
    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    model_dir = os.getenv("WHISPER_MODEL_DIR", "data/models")
    initial_prompt = os.getenv("WHISPER_INITIAL_PROMPT", "以下是中文语音的准确转录。")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stem = Path(audio_path).stem
    srt_path = output / f"{stem}.srt"
    markdown_path = output / f"{stem}_whisper.md"

    try:
        cache_key = (model_source, device, compute_type, model_dir)
        model = _MODEL_CACHE.get(cache_key)
        if model is None:
            model = WhisperModel(
                model_source,
                device=device,
                compute_type=compute_type,
                download_root=model_dir,
            )
            _MODEL_CACHE[cache_key] = model
        segments_iter, info = model.transcribe(
            audio_path,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            initial_prompt=initial_prompt or None,
        )
        segments = list(segments_iter)
    except Exception as exc:
        raise TranscriptionError(f"Faster-Whisper 转录失败：{exc}") from exc

    text_parts: list[str] = []
    srt_parts: list[str] = []
    for index, segment in enumerate(segments, start=1):
        text = (segment.text or "").strip()
        if not text:
            continue
        text_parts.append(text)
        srt_parts.extend([
            str(index),
            f"{_srt_timestamp(segment.start)} --> {_srt_timestamp(segment.end)}",
            text,
            "",
        ])

    text = "\n".join(text_parts).strip()
    if not text:
        raise TranscriptionError("Faster-Whisper 没有识别出有效语音内容。")

    srt_path.write_text("\n".join(srt_parts), encoding="utf-8")
    language = getattr(info, "language", "") or "unknown"
    markdown_path.write_text(
        f"# Whisper 转录\n\n**识别语言**: {language}\n\n---\n\n{text}\n",
        encoding="utf-8",
    )
    return TranscriptionResult(
        text=text,
        language=language,
        srt_path=str(srt_path),
        markdown_path=str(markdown_path),
    )
