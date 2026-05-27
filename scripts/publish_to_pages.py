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
import time
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
GIT_TIMEOUT_SECONDS = int(os.getenv("PUBLISH_GIT_TIMEOUT_SECONDS", "600"))
HTTP_USER_AGENT = "Mozilla/5.0 SecondBrainPodcastPublisher/1.0"


def remove_worktree():
    """Remove the temporary publish checkout, retrying transient macOS rmtree races."""
    path = Path(WORKTREE)
    if not path.exists():
        return
    for _ in range(3):
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return
        time.sleep(0.2)
    shutil.rmtree(path)


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


def github_https_url(repo_url: str) -> str | None:
    """Return a public HTTPS clone URL for GitHub SSH remotes."""
    prefix = "git@github.com:"
    if repo_url.startswith(prefix):
        repo_path = repo_url[len(prefix):]
        return f"https://github.com/{repo_path}"
    return None


def run_with_https_fallback(cmd: list[str], cwd: Path | str | None = None) -> str:
    """Run a git command, retrying GitHub SSH remotes via HTTPS for read-only operations."""
    try:
        return run(cmd, cwd=cwd)
    except SystemExit as exc:
        https_url = github_https_url(PAGES_REPO)
        if not https_url:
            raise

        retry = [https_url if part == PAGES_REPO else part for part in cmd]
        print(f"Retrying with HTTPS remote: {' '.join(retry)}")
        try:
            return run(retry, cwd=cwd)
        except SystemExit:
            raise exc


def branch_exists_remote() -> bool:
    def ls_remote(repo_url: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "ls-remote", "--heads", repo_url, PAGES_BRANCH],
            capture_output=True,
            text=True,
            env=command_env(),
            timeout=30,
        )

    try:
        result = ls_remote(PAGES_REPO)
    except subprocess.TimeoutExpired:
        https_url = github_https_url(PAGES_REPO)
        if not https_url:
            print(f"Command timed out after 30s: git ls-remote --heads {PAGES_REPO} {PAGES_BRANCH}")
            sys.exit(1)
        print(f"SSH ls-remote timed out; retrying with HTTPS remote: {https_url}")
        result = ls_remote(https_url)
    if result.returncode != 0:
        https_url = github_https_url(PAGES_REPO)
        if https_url and PAGES_REPO != https_url:
            print(f"SSH ls-remote failed; retrying with HTTPS remote: {https_url}")
            result = ls_remote(https_url)
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
        request = urllib.request.Request(
            f"{PAGES_URL}/podcast.xml",
            headers={"User-Agent": HTTP_USER_AGENT, "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
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
    remove_worktree()

    run_with_https_fallback([
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        PAGES_BRANCH,
        "--single-branch",
        PAGES_REPO,
        WORKTREE,
    ])
    run(["git", "remote", "set-url", "origin", PAGES_REPO], cwd=WORKTREE)

    try:
        audio_src = ROOT / "static" / "audio"
        audio_dst = Path(WORKTREE) / "audio"
        audio_dst.mkdir(exist_ok=True)
        Path(f"{WORKTREE}/.nojekyll").touch()

        # Copy new or changed audio files
        copied = 0
        for f in audio_src.glob("*.mp3"):
            dst = audio_dst / f.name
            if not dst.exists() or f.stat().st_size != dst.stat().st_size:
                shutil.copy2(f, dst)
                copied += 1
        print(f"Copied {copied} new or changed audio file(s).")

        # Copy new images
        images_src = ROOT / "static" / "images"
        images_dst = Path(WORKTREE) / "images"
        if images_src.exists():
            images_dst.mkdir(exist_ok=True)
            copied_imgs = 0
            for f in images_src.iterdir():
                dst = images_dst / f.name
                if not dst.exists() or f.stat().st_size != dst.stat().st_size:
                    shutil.copy2(f, dst)
                    copied_imgs += 1
            print(f"Copied {copied_imgs} new or changed image(s).")

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
        remove_worktree()

    return f"{PAGES_URL}/podcast.xml"


if __name__ == "__main__":
    rss_url = publish()
    print(f"\nRSS URL: {rss_url}")
    print("Add this URL to Apple Podcasts or any podcast app.")
