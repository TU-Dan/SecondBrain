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


def run(cmd: list[str], check=True, cwd: Path | str | None = None) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(result.stderr)
        sys.exit(1)
    return result.stdout.strip()


def branch_exists_remote() -> bool:
    out = subprocess.run(
        ["git", "ls-remote", "--heads", PAGES_REPO, PAGES_BRANCH],
        capture_output=True, text=True
    ).stdout
    return f"refs/heads/{PAGES_BRANCH}" in out


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
            cwd=WORKTREE, capture_output=True, text=True
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
