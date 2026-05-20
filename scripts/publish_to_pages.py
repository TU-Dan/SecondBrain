#!/usr/bin/env python3
"""
Publish podcast audio and RSS feed to the Pages source repository.

Usage:
    python scripts/publish_to_pages.py

Requires GITHUB_PAGES_URL in .env, e.g.:
    GITHUB_PAGES_URL=https://tu-dan.github.io/podcast_generator

Optional:
    GITHUB_PAGES_REPO=git@github.com:TU-Dan/podcast_generator.git
    GITHUB_PAGES_BRANCH=gh-pages
"""

import os
import sys
import shutil
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# Ensure project root is in path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv()

from services.rss import generate_rss_for_export

PAGES_URL = os.getenv("GITHUB_PAGES_URL", "").rstrip("/")
PAGES_REPO = os.getenv("GITHUB_PAGES_REPO", "git@github.com:TU-Dan/podcast_generator.git")
PAGES_BRANCH = os.getenv("GITHUB_PAGES_BRANCH", "gh-pages")
WORKTREE = ".pages-publish-workdir"
EPISODES_FILE = ROOT / "static" / "episodes.json"
GIT_TIMEOUT_SECONDS = 120


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    if PAGES_REPO.startswith("git@"):
        env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes -o ConnectTimeout=15")
    return env


def run(cmd: list[str], check=True, cwd: Path | str | None = None, timeout: int = GIT_TIMEOUT_SECONDS) -> str:
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            env=command_env(),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        sys.exit(1)
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(result.stderr)
        sys.exit(1)
    return result.stdout.strip()


def branch_exists_remote() -> bool:
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", PAGES_REPO, PAGES_BRANCH],
            capture_output=True,
            text=True,
            env=command_env(),
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        print(f"Command timed out after 30s: git ls-remote --heads {PAGES_REPO} {PAGES_BRANCH}")
        sys.exit(1)
    if result.returncode != 0:
        print(f"Command failed: git ls-remote --heads {PAGES_REPO} {PAGES_BRANCH}")
        print(result.stderr)
        sys.exit(result.returncode)
    out = result.stdout
    return f"refs/heads/{PAGES_BRANCH}" in out


def local_episode_count() -> int:
    import json

    if not EPISODES_FILE.exists():
        return 0
    with EPISODES_FILE.open("r", encoding="utf-8") as f:
        return len(json.load(f))


def remote_episode_count() -> int | None:
    if not PAGES_URL:
        return None
    try:
        with urllib.request.urlopen(f"{PAGES_URL}/podcast.xml", timeout=15) as response:
            xml = response.read()
        root = ET.fromstring(xml)
    except Exception as exc:
        print(f"Warning: could not check remote RSS before publishing: {exc}")
        return None

    channel = root.find("channel")
    if channel is None:
        return 0
    return len(channel.findall("item"))


def guard_against_accidental_shrink():
    """Refuse to publish if local metadata would shrink the public RSS feed."""
    if os.getenv("ALLOW_RSS_SHRINK") == "1":
        print("ALLOW_RSS_SHRINK=1 set; skipping RSS shrink guard.")
        return

    local_count = local_episode_count()
    remote_count = remote_episode_count()
    if remote_count is None:
        return

    if local_count < remote_count:
        print(
            "Error: refusing to publish because local static/episodes.json has "
            f"{local_count} episode(s), but the public RSS has {remote_count}."
        )
        print("Restore local episode metadata first, or set ALLOW_RSS_SHRINK=1 if this is intentional.")
        sys.exit(1)


def init_gh_pages():
    """Create an orphan Pages branch in the publishing repository."""
    import tempfile
    print(f"Initializing {PAGES_BRANCH} branch in {PAGES_REPO}...")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run(["git", "init"], cwd=tmp_path)
        run(["git", "checkout", "-b", PAGES_BRANCH], cwd=tmp_path)
        Path(f"{tmp}/.nojekyll").touch()
        Path(f"{tmp}/audio").mkdir(exist_ok=True)
        run(["git", "add", "."], cwd=tmp_path)
        run(["git", "commit", "-m", "Initialize Pages podcast hosting"], cwd=tmp_path)
        run(["git", "remote", "add", "origin", PAGES_REPO], cwd=tmp_path)
        run(["git", "push", "-u", "origin", PAGES_BRANCH], cwd=tmp_path)
    print(f"{PAGES_BRANCH} branch created.")


def publish() -> str:
    """Sync audio files and podcast.xml to the Pages repo. Returns public RSS URL."""
    if not PAGES_URL:
        print("Error: GITHUB_PAGES_URL is not set in .env")
        print("Add this line to .env:")
        print("  GITHUB_PAGES_URL=https://tu-dan.github.io/podcast_generator")
        sys.exit(1)

    guard_against_accidental_shrink()

    # Init branch if needed
    if not branch_exists_remote():
        init_gh_pages()

    # Clean up any leftover checkout
    if Path(WORKTREE).exists():
        shutil.rmtree(WORKTREE)

    run([
        "git",
        "clone",
        "--branch",
        PAGES_BRANCH,
        "--single-branch",
        PAGES_REPO,
        WORKTREE,
    ])

    try:
        audio_src = ROOT / "static" / "audio"
        audio_dst = Path(WORKTREE) / "audio"
        audio_dst.mkdir(exist_ok=True)
        Path(f"{WORKTREE}/.nojekyll").touch()

        # Copy new audio files
        copied = 0
        for f in audio_src.glob("*.mp3"):
            dst = audio_dst / f.name
            if not dst.exists():
                shutil.copy2(f, dst)
                copied += 1
        print(f"Copied {copied} new audio file(s).")

        # Copy new images
        images_src = ROOT / "static" / "images"
        images_dst = Path(WORKTREE) / "images"
        if images_src.exists():
            images_dst.mkdir(exist_ok=True)
            copied_imgs = 0
            for f in images_src.iterdir():
                dst = images_dst / f.name
                if not dst.exists():
                    shutil.copy2(f, dst)
                    copied_imgs += 1
            print(f"Copied {copied_imgs} new image(s).")

        # Regenerate podcast.xml with GitHub Pages URLs
        generate_rss_for_export(PAGES_URL, f"{WORKTREE}/podcast.xml")
        print(f"Generated podcast.xml → {PAGES_URL}/podcast.xml")

        # Commit and push. Cloudflare Pages deploys from this repository/branch.
        run(["git", "add", "-A"], cwd=WORKTREE)
        result = subprocess.run(
            ["git", "commit", "-m", "Update podcast episodes"],
            cwd=WORKTREE,
            capture_output=True,
            text=True,
            env=command_env(),
            timeout=GIT_TIMEOUT_SECONDS,
        )
        if "nothing to commit" in result.stdout:
            print("Nothing new to publish.")
        else:
            if result.returncode != 0:
                print(result.stderr or result.stdout)
                sys.exit(result.returncode)
            run(["git", "push", "origin", PAGES_BRANCH], cwd=WORKTREE)
            print(f"Published to {PAGES_REPO}#{PAGES_BRANCH}.")
            print(f"Cloudflare Pages will deploy: {PAGES_URL}/podcast.xml")

    finally:
        shutil.rmtree(WORKTREE, ignore_errors=True)

    return f"{PAGES_URL}/podcast.xml"


if __name__ == "__main__":
    rss_url = publish()
    print(f"\nRSS URL: {rss_url}")
    print("Add this URL to Apple Podcasts or any podcast app.")
