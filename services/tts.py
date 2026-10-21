import asyncio
import json
import os
import re
import urllib.error
import urllib.request
import uuid

import edge_tts

DEFAULT_VOICE = "zh-CN-YunxiNeural"

VOICES = {
    "zh-CN-XiaoxiaoNeural": "晓晓 (女声·温柔)",
    "zh-CN-XiaoyiNeural": "晓伊 (女声·活泼)",
    "zh-CN-YunxiNeural": "云希 (男声·活泼)",
    "zh-CN-YunyangNeural": "云扬 (男声·专业)",
    "zh-CN-YunjianNeural": "云健 (男声·成熟)",
}
MINIMAX_URL = "https://api.minimax.cn/v1/t2a_v2"
MINIMAX_REQUEST_TIMEOUT_SECONDS = 120

# edge-tts struggles with very long inputs; chunk at this many chars
TTS_CHUNK_SIZE = 2000
TTS_REQUEST_TIMEOUT_SECONDS = 120


def clean_text_for_tts(text: str) -> str:
    """Remove markdown and symbols that TTS would read aloud."""
    # Remove images: ![alt](url) -> ''
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
    # Remove markdown links: [text](url) -> text
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove bold/italic (single-line only, no DOTALL to avoid eating paragraphs)
    text = re.sub(r'\*{1,3}([^\n*]*?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,2}([^\n_]*?)_{1,2}', r'\1', text)
    # Remove headings: ## Title -> Title (with or without space after #)
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    # Remove inline code: `code` -> code
    text = re.sub(r'`+([^`\n]*)`+', r'\1', text)
    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Remove blockquote markers
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    # Remove table separators like |---|---|
    text = re.sub(r'^\|[-| :]+\|$', '', text, flags=re.MULTILINE)
    # Remove table pipes (keep cell content)
    text = re.sub(r'\|', ' ', text)
    # Remove remaining stray asterisks and # sequences
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#{2,}', '', text)
    text = re.sub(r'(?<![A-Za-z])#(?![A-Za-z0-9])', '', text)

    # -- Characters that crash edge-tts when isolated --
    # Replace Chinese ellipsis / em-dash with comma (speakable pause)
    text = text.replace('\u2026', ',')      # … → ,
    text = text.replace('\u2014', ',')      # — → ,
    text = text.replace('\u2013', ',')      # – → ,
    # Replace arrows and bullets with empty
    text = re.sub(r'[\u2190-\u21ff]', '', text)    # arrows ← → ↑ ↓ etc.
    text = re.sub(r'[\u2022\u2605\u2606\u25cf\u25cb\u25a0\u25a1]', '', text)  # bullets/stars/squares
    # Replace ... with comma
    text = re.sub(r'\.{2,}', ',', text)
    # Replace repeated punctuation like 。。。 with single
    text = re.sub(r'([。！？!?])\1+', r'\1', text)
    # Remove tilde ～
    text = text.replace('\uff5e', '')
    # Remove middot · (not speakable alone)
    text = text.replace('\u00b7', ' ')
    # Remove smart quotes (not speakable alone)
    text = re.sub(r'[\u201c\u201d\u2018\u2019]', '', text)

    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Collapse multiple commas/spaces
    text = re.sub(r'[,，]{2,}', '，', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def _has_speech_content(text: str) -> bool:
    """Return True if text has at least one letter or digit (not just punctuation/whitespace)."""
    return bool(re.search(r'[\w\u4e00-\u9fff]', text))


def _split_for_tts(text: str, max_chars: int = TTS_CHUNK_SIZE) -> list[str]:
    """Split text into chunks at sentence boundaries for edge-tts."""
    sentences = re.split(r'(?<=[。！？!?\n])', text)
    chunks, current = [], ''
    for s in sentences:
        if len(current) + len(s) > max_chars and current:
            chunks.append(current.strip())
            current = s
        else:
            current += s
    if current.strip():
        chunks.append(current.strip())
    # Filter out chunks with no actual speech content (punctuation-only fragments)
    return [c for c in chunks if _has_speech_content(c)] or ([text] if _has_speech_content(text) else [])


async def generate_audio(text: str, voice: str = DEFAULT_VOICE, output_dir: str = "static/audio") -> str:
    """Generate MP3 from text using the selected voice provider."""
    os.makedirs(output_dir, exist_ok=True)

    text = clean_text_for_tts(text)
    if not text:
        raise ValueError("Text is empty after cleaning — nothing to synthesize.")

    if voice.startswith("minimax:"):
        return await asyncio.to_thread(_generate_minimax_audio, text, voice.removeprefix("minimax:"), output_dir)

    print(f"[TTS] {len(text)} chars, voice={voice}")

    filename = f"{uuid.uuid4().hex}.mp3"
    output_path = os.path.join(output_dir, filename)

    chunks = _split_for_tts(text)
    if not chunks:
        raise ValueError("No speakable content found after cleaning.")

    print(f"[TTS] {len(chunks)} chunk(s), sizes: {[len(c) for c in chunks]}")

    async def synth_chunk(chunk: str, out: str) -> None:
        """Synthesize one chunk with bounded retries."""
        last_failure = "语音服务未返回音频"
        for attempt in range(3):
            try:
                communicate = edge_tts.Communicate(chunk, voice)
                await asyncio.wait_for(communicate.save(out), timeout=TTS_REQUEST_TIMEOUT_SECONDS)
                # Verify non-empty output
                if os.path.getsize(out) > 0:
                    return
                print(f"[TTS] Chunk produced empty file, attempt {attempt + 1}/3")
            except asyncio.TimeoutError:
                last_failure = f"单段合成超时（{TTS_REQUEST_TIMEOUT_SECONDS} 秒）"
                print(f"[TTS] Chunk timed out (attempt {attempt + 1}/3)")
            except Exception as e:
                if getattr(e, "status", None) == 403:
                    if os.path.exists(out):
                        os.remove(out)
                    raise RuntimeError("TTS 语音服务拒绝连接（HTTP 403）。请更新 edge-tts 后重试。") from e
                last_failure = type(e).__name__
                print(f"[TTS] Chunk failed (attempt {attempt + 1}/3): {e}")
            if os.path.exists(out):
                os.remove(out)
            if attempt < 2:
                await asyncio.sleep(1 + attempt)
        # Log the problematic chunk for debugging
        print(f"[TTS] Giving up on chunk ({len(chunk)} chars): {chunk[:80]!r}...")
        raise RuntimeError(f"TTS 语音合成失败：{last_failure}，重试 3 次仍未成功。")

    if len(chunks) == 1:
        await synth_chunk(chunks[0], output_path)
    else:
        parts = []
        for chunk in chunks:
            tmp_path = os.path.join(output_dir, f"_tmp_{uuid.uuid4().hex}.mp3")
            try:
                await synth_chunk(chunk, tmp_path)
                with open(tmp_path, 'rb') as f:
                    parts.append(f.read())
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        with open(output_path, 'wb') as f:
            for part in parts:
                f.write(part)

    return filename


def _generate_minimax_audio(text: str, voice_id: str, output_dir: str) -> str:
    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("MiniMax 语音合成未配置 MINIMAX_API_KEY。")
    if not voice_id:
        raise ValueError("MiniMax 音色 ID 不能为空。")

    filename = f"{uuid.uuid4().hex}.mp3"
    output_path = os.path.join(output_dir, filename)
    chunks = [
        chunk[i:i + 3000]
        for chunk in _split_for_tts(text, max_chars=3000)
        for i in range(0, len(chunk), 3000)
    ]
    if not chunks:
        raise ValueError("No speakable content found after cleaning.")

    try:
        with open(output_path, "wb") as audio_file:
            for chunk in chunks:
                payload = {
                    "model": os.getenv("MINIMAX_TTS_MODEL", "speech-2.8-turbo"),
                    "text": chunk,
                    "stream": False,
                    "output_format": "hex",
                    "voice_setting": {"voice_id": voice_id},
                    "audio_setting": {"format": "mp3"},
                }
                request = urllib.request.Request(
                    os.getenv("MINIMAX_TTS_URL", MINIMAX_URL),
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(request, timeout=MINIMAX_REQUEST_TIMEOUT_SECONDS) as response:
                        result = json.load(response)
                except urllib.error.HTTPError as exc:
                    raise RuntimeError(f"MiniMax 语音合成请求失败（HTTP {exc.code}）。") from exc
                except urllib.error.URLError as exc:
                    raise RuntimeError("MiniMax 语音服务连接失败。") from exc

                base_resp = result.get("base_resp") or {}
                if base_resp.get("status_code") != 0:
                    raise RuntimeError(
                        f"MiniMax 语音合成失败（{base_resp.get('status_code')}：{base_resp.get('status_msg')}）。"
                    )
                audio_hex = (result.get("data") or {}).get("audio")
                if not audio_hex:
                    raise RuntimeError("MiniMax 语音服务返回空音频。")
                try:
                    audio_file.write(bytes.fromhex(audio_hex))
                except ValueError as exc:
                    raise RuntimeError("MiniMax 语音服务返回无效音频。") from exc
    except Exception:
        os.remove(output_path)
        raise

    return filename


def generate_audio_sync(text: str, voice: str = DEFAULT_VOICE, output_dir: str = "static/audio") -> str:
    """Synchronous wrapper for generate_audio."""
    return asyncio.run(generate_audio(text, voice, output_dir))
