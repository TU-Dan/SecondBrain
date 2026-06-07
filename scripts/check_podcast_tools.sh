#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOUYIN_URL="${DOUYIN_DOWNLOADER_BASE_URL:-http://127.0.0.1:18080}"
PYTHON_BIN="${PYTHON_BIN:-python}"

failed=0

if command -v ffmpeg >/dev/null; then
  echo "FFmpeg: OK"
else
  echo "FFmpeg: 未安装"
  failed=1
fi

if "$PYTHON_BIN" -c "import faster_whisper" >/dev/null 2>&1; then
  echo "Faster-Whisper: OK"
else
  echo "Faster-Whisper: 未安装"
  failed=1
fi

if [ -x "$ROOT/tools/BBDown/BBDown" ] && "$ROOT/tools/BBDown/BBDown" --help >/dev/null 2>&1; then
  echo "BBDown: OK"
else
  echo "BBDown: 未安装或不可执行"
  failed=1
fi

if curl -fsS --max-time 3 "$DOUYIN_URL/api/v1/health" >/dev/null; then
  echo "Douyin Downloader: OK"
else
  echo "Douyin Downloader 未运行。启动命令: bash scripts/start_douyin_downloader.sh"
  failed=1
fi

if grep -Eq '^[[:space:]]+(ttwid|odin_tt):[[:space:]]+\"?[^\"[:space:]]+' "$ROOT/tools/douyin-downloader/config.yml" 2>/dev/null; then
  echo "Douyin Cookie: OK"
else
  echo "Douyin Cookie: 未配置；公开内容触发反爬时需要先登录获取 Cookie"
fi

if [ "$failed" -ne 0 ]; then
  echo "请先运行: bash scripts/setup_podcast_tools_macos.sh"
  exit 1
fi

echo "Podcast tools: OK"
