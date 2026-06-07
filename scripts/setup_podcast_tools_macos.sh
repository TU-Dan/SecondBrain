#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/tools"
BBDOWN_VERSION="1.6.3"
DOUYIN_COMMIT="dc7e967b1680cf18beae9857fb99eb43fe0aeee6"
DOUYIN_REPO="${DOUYIN_REPO:-https://github.com/jiji262/douyin-downloader.git}"
PYTHON_BIN="${PYTHON_BIN:-python}"

mkdir -p \
  "$TOOLS/BBDown" \
  "$ROOT/data/cookies" \
  "$ROOT/data/models" \
  "$ROOT/data/podcast_media"

command -v ffmpeg >/dev/null || {
  echo "ffmpeg 未安装。请先运行: brew install ffmpeg"
  exit 1
}

echo "Installing Faster-Whisper..."
"$PYTHON_BIN" -m pip install "faster-whisper>=1.1,<2"

if [ ! -x "$TOOLS/BBDown/BBDown" ]; then
  echo "Downloading BBDown ${BBDOWN_VERSION} for macOS arm64..."
  curl -L \
    "https://github.com/nilaoda/BBDown/releases/download/${BBDOWN_VERSION}/BBDown_1.6.3_20240814_osx-arm64.zip" \
    -o "$TOOLS/BBDown/BBDown.zip"
  unzip -o "$TOOLS/BBDown/BBDown.zip" -d "$TOOLS/BBDown"
  chmod +x "$TOOLS/BBDown/BBDown"
fi

if [ ! -d "$TOOLS/douyin-downloader/.git" ]; then
  echo "Cloning Douyin Downloader..."
  git clone "$DOUYIN_REPO" "$TOOLS/douyin-downloader"
fi
if git -C "$TOOLS/douyin-downloader" cat-file -e "${DOUYIN_COMMIT}^{commit}" 2>/dev/null; then
  echo "Douyin Downloader pinned commit already available locally."
else
  echo "Fetching pinned Douyin Downloader commit..."
  git -C "$TOOLS/douyin-downloader" fetch origin "$DOUYIN_COMMIT"
fi
git -C "$TOOLS/douyin-downloader" checkout "$DOUYIN_COMMIT"
if [ ! -f "$TOOLS/douyin-downloader/config.yml" ]; then
  cp "$TOOLS/douyin-downloader/config.example.yml" "$TOOLS/douyin-downloader/config.yml"
  sed -i '' -E 's/(YOUR_[A-Z_]+)//g' "$TOOLS/douyin-downloader/config.yml"
fi

if [ ! -d "$TOOLS/douyin-downloader/.venv" ]; then
  "$PYTHON_BIN" -m venv --system-site-packages "$TOOLS/douyin-downloader/.venv"
elif ! "$TOOLS/douyin-downloader/.venv/bin/python" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "Enabling access to existing FastAPI/Uvicorn packages..."
  "$PYTHON_BIN" -m venv --upgrade --system-site-packages "$TOOLS/douyin-downloader/.venv"
fi
"$TOOLS/douyin-downloader/.venv/bin/pip" install -r "$TOOLS/douyin-downloader/requirements.txt"
if ! "$TOOLS/douyin-downloader/.venv/bin/python" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  "$TOOLS/douyin-downloader/.venv/bin/pip" install "fastapi>=0.110,<1" "uvicorn>=0.27,<1"
fi

echo
echo "Podcast tools ready."
echo "Start Douyin Downloader with:"
echo "  bash scripts/start_douyin_downloader.sh"
echo
echo "Optional B站 Cookie file:"
echo "  data/cookies/bilibili.txt"
echo
echo "If Douyin reports anti-bot or cookie_required, capture a fresh cookie:"
echo "  bash scripts/capture_douyin_cookie.sh"
