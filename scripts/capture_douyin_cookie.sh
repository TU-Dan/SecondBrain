#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$ROOT/tools/douyin-downloader"

if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
  echo "Douyin Downloader 尚未安装，请先运行: bash scripts/setup_podcast_tools_macos.sh"
  exit 1
fi

cd "$APP_DIR"
exec .venv/bin/python -m tools.cookie_fetcher --config config.yml "$@"
