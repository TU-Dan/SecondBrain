#!/usr/bin/env python3
"""
Publish podcast audio and RSS feed to GitHub Pages (gh-pages branch).

Usage:
    python scripts/publish_to_pages.py

Requires GITHUB_PAGES_URL in .env, e.g.:
    GITHUB_PAGES_URL=https://tu-dan.github.io/podcast_generator
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
WORKTREE = ".gh-pages-publish"


def run(cmd: str, check=True) -> str:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {cmd}")
        print(result.stderr)
        sys.exit(1)
    return result.stdout.strip()


def branch_exists_remote() -> bool:
    out = subprocess.run(
        "git ls-remote --heads origin gh-pages",
        shell=True, capture_output=True, text=True
    ).stdout
    return "gh-pages" in out


def init_gh_pages():
    """Create an orphan gh-pages branch and push it."""
    import tempfile
    print("Initializing gh-pages branch...")

    remote = run("git remote get-url origin")
    with tempfile.TemporaryDirectory() as tmp:
        run(f"git -C {tmp} init")
        run(f"git -C {tmp} checkout -b gh-pages")
        Path(f"{tmp}/.nojekyll").touch()
        Path(f"{tmp}/audio").mkdir(exist_ok=True)
        run(f"git -C {tmp} add .")
        run(f'git -C {tmp} commit -m "Initialize GitHub Pages for podcast hosting"')
        run(f"git -C {tmp} remote add origin {remote}")
        run(f"git -C {tmp} push origin gh-pages")
    print("gh-pages branch created.")


def publish() -> str:
    """Sync audio files and podcast.xml to gh-pages. Returns public RSS URL."""
    if not PAGES_URL:
        print("Error: GITHUB_PAGES_URL is not set in .env")
        print("Add this line to .env:")
        print("  GITHUB_PAGES_URL=https://tu-dan.github.io/podcast_generator")
        sys.exit(1)

    # Init branch if needed
    if not branch_exists_remote():
        init_gh_pages()

    # Ensure local branch tracks remote gh-pages
    run("git fetch origin gh-pages", check=False)
    local_branches = run("git branch --list gh-pages")
    if not local_branches.strip():
        run("git branch gh-pages origin/gh-pages")

    # Clean up any leftover worktree
    if Path(WORKTREE).exists():
        run(f"git worktree remove --force {WORKTREE}", check=False)

    run(f"git worktree add {WORKTREE} gh-pages")

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

        # Commit and push
        run(f"git -C {WORKTREE} add -A")
        result = subprocess.run(
            'git -C .gh-pages-publish commit -m "Update podcast episodes"',
            shell=True, capture_output=True, text=True
        )
        if "nothing to commit" in result.stdout:
            print("Nothing new to publish.")
        else:
            run(f"git -C {WORKTREE} push origin gh-pages")
            print(f"Published! RSS feed: {PAGES_URL}/podcast.xml")

    finally:
        run(f"git worktree remove {WORKTREE}", check=False)

    return f"{PAGES_URL}/podcast.xml"


if __name__ == "__main__":
    rss_url = publish()
    print(f"\nRSS URL: {rss_url}")
    print("Add this URL to Apple Podcasts or any podcast app.")
