import os
import re
import shutil
import subprocess
import tempfile
import uuid
import html as html_lib
import urllib.request
from urllib.parse import parse_qs, urlparse
import yt_dlp
import trafilatura
from PyPDF2 import PdfReader


FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class ExtractionError(RuntimeError):
    """Raised when a source cannot be extracted for a known actionable reason."""


def _format_yt_dlp_error(error: Exception, platform_label: str) -> str:
    message = str(error)
    if "Sign in to confirm" in message or "not a bot" in message:
        return (
            f"{platform_label} 触发了反机器人验证，yt-dlp 无法匿名提取字幕或音频。"
            "请先在本机浏览器确认该视频可访问；如仍失败，可在启动服务前设置 "
            "SECOND_BRAIN_USE_BROWSER_COOKIES=1 允许 yt-dlp 使用浏览器登录态。"
        )
    if "Video unavailable" in message:
        return f"{platform_label} 视频不可用。请确认链接是公开可访问的单个视频，而不是私密、删除或地区限制视频。"
    return f"{platform_label} 内容提取失败：{message}"


def _fetch_html(url: str) -> str | None:
    """Fetch HTML with trafilatura, falling back to curl_cffi for sites with bot protection."""
    html = trafilatura.fetch_url(url)
    if html:
        return html

    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(url, impersonate="chrome", headers=FETCH_HEADERS, timeout=20)
        if resp.status_code == 200 and resp.text:
            return resp.text
    except Exception as e:
        print(f"curl_cffi fallback failed: {e}")

    try:
        req = urllib.request.Request(url, headers=FETCH_HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read()
        return body.decode("utf-8", errors="replace") if body else None
    except Exception as e:
        print(f"urllib fallback failed: {e}")

    try:
        result = subprocess.run(
            [
                "curl",
                "-L",
                "--compressed",
                "--max-time",
                "25",
                "-A",
                FETCH_HEADERS["User-Agent"],
                "-H",
                f"Accept: {FETCH_HEADERS['Accept']}",
                "-H",
                f"Accept-Language: {FETCH_HEADERS['Accept-Language']}",
                url,
            ],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.decode("utf-8", errors="replace")
        if result.stderr:
            print(f"curl fallback failed: {result.stderr.decode('utf-8', errors='replace')[:300]}")
    except Exception as e:
        print(f"curl fallback failed: {e}")

    return None


def _extract_og_image(html: str) -> str | None:
    m = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    )
    if not m:
        m = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            html, re.IGNORECASE
        )
    return m.group(1) if m else None


def _extract_title(html: str) -> str | None:
    og = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if og:
        return re.sub(r"\s+", " ", og.group(1)).strip()

    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    title = re.sub(r"<[^>]+>", "", m.group(1))
    return re.sub(r"\s+", " ", title).strip() or None


def detect_url_platform(url: str) -> str:
    lower = url.lower()
    if "youtube.com" in lower or "youtu.be" in lower:
        return "youtube"
    if "douyin.com" in lower or "iesdouyin.com" in lower:
        return "douyin"
    if "bilibili.com" in lower or "b23.tv" in lower:
        return "bilibili"
    if "mp.weixin.qq.com" in lower:
        return "wechat"
    return "url"


def normalize_video_url(url: str) -> str:
    """Return a canonical single-video URL for video platforms.

    User-pasted YouTube links often include playlist state like list/index. The
    generator works on one source item at a time, so keep the video id and drop
    playlist/navigation query parameters before handing the URL to yt-dlp.
    """
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    path = parsed.path

    if "youtu.be" in host:
        video_id = path.strip("/").split("/")[0]
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"

    if "youtube.com" in host:
        query = parse_qs(parsed.query)
        video_id = (query.get("v") or [""])[0]
        if not video_id and path.startswith("/shorts/"):
            video_id = path.split("/")[2] if len(path.split("/")) > 2 else ""
        if not video_id and path.startswith("/embed/"):
            video_id = path.split("/")[2] if len(path.split("/")) > 2 else ""
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"

    return url.strip()


def extract_from_url(url: str) -> tuple[str, str | None]:
    """Extract text and og:image thumbnail from a web page."""
    html = _fetch_html(url)
    if not html:
        return "", None

    text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
    if len(text.strip()) < 200:
        text = trafilatura.extract(
            html,
            favor_precision=False,
            favor_recall=True,
            include_comments=False,
            include_tables=False,
        ) or text
    thumbnail = _extract_og_image(html)
    title = _extract_title(html)
    if title and text and not text.lstrip().startswith(title):
        text = f"{title}\n\n{text}"
    return text, thumbnail


def _clean_html_text(fragment: str) -> str:
    fragment = re.sub(r"(?is)<script[^>]*>.*?</script>", "", fragment)
    fragment = re.sub(r"(?is)<style[^>]*>.*?</style>", "", fragment)
    fragment = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    fragment = re.sub(r"(?i)</p\s*>", "\n\n", fragment)
    fragment = re.sub(r"(?i)</section\s*>", "\n", fragment)
    text = re.sub(r"<[^>]+>", "", fragment)
    text = html_lib.unescape(text)
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_js_string(html: str, name: str) -> str:
    m = re.search(rf"var\s+{re.escape(name)}\s*=\s*(['\"])(.*?)\1\s*;", html, re.DOTALL)
    if not m:
        return ""
    value = m.group(2)
    try:
        value = bytes(value, "utf-8").decode("unicode_escape")
    except Exception:
        pass
    return html_lib.unescape(value).strip()


def extract_from_wechat(url: str) -> tuple[str, str | None]:
    html = _fetch_html(url)
    if not html:
        return "", None

    title = _extract_js_string(html, "msg_title") or _extract_title(html) or ""
    desc = _extract_js_string(html, "msg_desc")
    thumbnail = _extract_js_string(html, "msg_cdn_url") or _extract_og_image(html)

    body = ""
    m = re.search(
        r'<div[^>]+id=["\']js_content["\'][^>]*>(.*?)</div>\s*</div>\s*<script',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        body = _clean_html_text(m.group(1))

    if len(body) < 200:
        body = trafilatura.extract(html, include_comments=False, include_tables=False) or body

    parts = [p for p in [title, desc, body] if p]
    return "\n\n".join(parts).strip(), thumbnail


def _ydl_base_opts(
    tmpdir: str,
    subtitle_langs: list[str] | None = None,
    write_subtitles: bool = True,
) -> dict:
    opts = {
        'skip_download': True,
        'writesubtitles': write_subtitles,
        'writeautomaticsub': write_subtitles,
        'subtitleslangs': subtitle_langs or ['zh-Hans', 'zh-Hant', 'zh', 'en'],
        'subtitlesformat': 'vtt/srt/best',
        'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'ignoreerrors': False,
        'noplaylist': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['tv_embedded', 'android', 'web'],
            }
        },
    }
    if os.getenv("SECOND_BRAIN_USE_BROWSER_COOKIES") == "1":
        opts['cookiesfrombrowser'] = ('chrome',)
    return opts


def _preferred_caption_languages(info: dict) -> list[str]:
    available = set((info.get("subtitles") or {}).keys())
    available.update((info.get("automatic_captions") or {}).keys())
    if not available:
        return []

    candidates: list[str] = []
    preferences = ["en", "en-US", "en-GB", "zh-Hans", "zh-Hant", "zh"]
    for preferred in preferences:
        for lang in sorted(available):
            if lang == preferred or lang.startswith(f"{preferred}-"):
                if lang not in candidates:
                    candidates.append(lang)
    for lang in sorted(available):
        if lang not in candidates and (lang.startswith("en") or lang.startswith("zh")):
            candidates.append(lang)
    return candidates


def _parse_vtt(path: str) -> str:
    """Strip VTT timing/metadata lines, return plain transcript text."""
    seen = set()
    lines = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or '-->' in line or line.startswith('WEBVTT') or line.isdigit():
                continue
            if line.startswith("Kind:") or line.startswith("Language:"):
                continue
            # Strip inline VTT tags like <00:00:01.000><c>text</c>
            line = re.sub(r'<[^>]+>', '', line)
            if line and line not in seen:
                seen.add(line)
                lines.append(line)
    return ' '.join(lines)


def _parse_subtitle_file(path: str) -> str:
    if path.endswith(".vtt") or path.endswith(".srt"):
        return _parse_vtt(path)
    return ""


def _build_video_text(info: dict, sub_text: str, platform_label: str) -> str:
    title = info.get("title") or ""
    description = info.get("description") or ""
    uploader = info.get("uploader") or info.get("channel") or info.get("creator") or ""
    duration = info.get("duration")
    tags = info.get("tags") or []

    meta = []
    if title:
        meta.append(title)
    if uploader:
        meta.append(f"作者：{uploader}")
    meta.append(f"平台：{platform_label}")
    if duration:
        meta.append(f"时长：{duration} 秒")
    if tags:
        meta.append("标签：" + "、".join(str(t) for t in tags[:12]))

    content_parts = ["\n".join(meta)]
    if sub_text:
        content_parts.append("视频字幕/转写：\n" + sub_text)
    if description and description not in sub_text:
        content_parts.append("视频简介：\n" + description)
    return "\n\n".join(part for part in content_parts if part).strip()


def extract_from_video_platform(url: str, platform_label: str) -> tuple[str, str | None]:
    """Extract subtitles/metadata from a video platform supported by yt-dlp."""
    with tempfile.TemporaryDirectory() as tmpdir:
        opts = _ydl_base_opts(tmpdir)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)

            if not info:
                return "", None

            sub_text = ""
            for fname in os.listdir(tmpdir):
                if fname.endswith((".vtt", ".srt")):
                    try:
                        sub_text = _parse_subtitle_file(os.path.join(tmpdir, fname))
                        if sub_text:
                            break
                    except Exception as e:
                        print(f"Warning: subtitle parse error ({e})")

            text = _build_video_text(info, sub_text, platform_label)
            thumbnail = info.get("thumbnail")
            return text, thumbnail

        except Exception as e:
            message = _format_yt_dlp_error(e, platform_label)
            print(f"Error extracting from {platform_label}: {message}")
            raise ExtractionError(message) from e


def extract_from_youtube(url: str) -> tuple[str, str | None]:
    """Extract subtitles (or description) and thumbnail from a YouTube video."""
    url = normalize_video_url(url)
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            metadata_opts = _ydl_base_opts(tmpdir, write_subtitles=False)
            with yt_dlp.YoutubeDL(metadata_opts) as ydl:
                info = ydl.extract_info(url, download=False)

        except Exception as e:
            message = _format_yt_dlp_error(e, "YouTube")
            print(f"Error extracting from YouTube: {message}")
            raise ExtractionError(message) from e

        if not info:
            return "", None

        thumbnail = info.get('thumbnail')
        errors: list[str] = []
        for lang in _preferred_caption_languages(info):
            with tempfile.TemporaryDirectory() as subdir:
                try:
                    opts = _ydl_base_opts(subdir, subtitle_langs=[lang], write_subtitles=True)
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        subtitle_info = ydl.extract_info(url, download=True) or info

                    sub_text = ""
                    for fname in os.listdir(subdir):
                        if fname.endswith(('.vtt', '.srt')):
                            try:
                                sub_text = _parse_subtitle_file(os.path.join(subdir, fname))
                                if sub_text:
                                    break
                            except Exception as e:
                                print(f"Warning: VTT parse error ({e})")

                    if sub_text:
                        return _build_video_text(subtitle_info, sub_text, "YouTube"), thumbnail
                except Exception as e:
                    errors.append(_format_yt_dlp_error(e, f"YouTube 字幕 {lang}"))
                    continue

        text = _build_video_text(info, "", "YouTube")
        if text.strip():
            if errors:
                print("Warning: YouTube subtitles unavailable; using metadata fallback. " + " | ".join(errors[:2]))
            return text.strip(), thumbnail

        if errors:
            raise ExtractionError(errors[0])
        return "", thumbnail


def extract_from_pdf(file_path: str) -> tuple[str, None]:
    """Extract text from a PDF file."""
    text = ""
    try:
        reader = PdfReader(file_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text, None


def extract_from_txt(file_path: str) -> tuple[str, None]:
    """Extract text from a TXT file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read(), None
    except Exception as e:
        print(f"Error reading TXT: {e}")
        return "", None


def download_youtube_audio(url: str, out_dir: str = "static/audio") -> str | None:
    """Download audio from a yt-dlp supported video URL.
    Returns filename or None."""
    url = normalize_video_url(url)
    os.makedirs(out_dir, exist_ok=True)
    out_name = uuid.uuid4().hex

    with tempfile.TemporaryDirectory() as tmpdir:
        dest_name = f"{out_name}.mp3"
        opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(tmpdir, f"{out_name}.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }],
            "quiet": True,
            "no_warnings": True,
            "retries": 3,
            "fragment_retries": 3,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print(f"Audio download failed: {_format_yt_dlp_error(e, 'YouTube')}")
            return None

        mp3_path = os.path.join(tmpdir, dest_name)
        if os.path.exists(mp3_path):
            shutil.copy(mp3_path, os.path.join(out_dir, dest_name))
            print(f"Audio saved: {dest_name}")
            return dest_name

    print("Audio download: no output file found")
    return None


def extract_content(source: str, source_type: str = 'url') -> tuple[str, str | None]:
    """
    Main entry point. Returns (text, thumbnail_url | None).
    source_type: 'url' | 'youtube' | 'douyin' | 'bilibili' | 'wechat' | 'pdf' | 'txt'
    """
    platform = detect_url_platform(source) if source.startswith("http") else source_type
    if source_type == 'youtube' or platform == 'youtube':
        return extract_from_youtube(source)
    elif source_type == 'douyin' or platform == 'douyin':
        return extract_from_video_platform(source, "抖音")
    elif source_type == 'bilibili' or platform == 'bilibili':
        return extract_from_video_platform(source, "B站")
    elif source_type == 'wechat' or platform == 'wechat':
        return extract_from_wechat(source)
    elif source_type == 'url' or source.startswith('http'):
        return extract_from_url(source)
    elif source_type == 'pdf':
        return extract_from_pdf(source)
    elif source_type == 'txt':
        return extract_from_txt(source)
    return "", None
