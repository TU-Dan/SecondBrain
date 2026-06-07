#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$ROOT/tools/douyin-downloader"

if [ ! -x "$APP_DIR/.venv/bin/python" ] || \
  ! "$APP_DIR/.venv/bin/python" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "Douyin Downloader 尚未安装，请先运行 scripts/setup_podcast_tools_macos.sh"
  exit 1
fi

cd "$APP_DIR"
exec .venv/bin/python run.py --serve --serve-host 127.0.0.1 --serve-port 18080
