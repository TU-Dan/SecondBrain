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

import hashlib
import json
import os
import sys
import shutil
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlparse

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
DEPLOY_TIMEOUT_SECONDS = int(os.getenv("PUBLISH_DEPLOY_TIMEOUT_SECONDS", "240"))
MAX_PAGES_FILE_BYTES = 24 * 1024 * 1024
HTTP_USER_AGENT = "Mozilla/5.0 SecondBrainPodcastPublisher/1.0"


def remove_worktree():
    """Remove an incomplete publish checkout, retrying transient macOS rmtree races."""
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


def prepare_worktree() -> None:
    """Reuse the publisher checkout so historical audio is not cloned on every run."""
    checkout = Path(WORKTREE)
    if checkout.exists():
        if not (checkout / ".git").is_dir():
            raise RuntimeError(f"Publish checkout is not a Git repository: {checkout}")
        if not run(["git", "rev-parse", "--verify", "HEAD"], check=False, cwd=checkout):
            remove_worktree()
        else:
            remote = run(["git", "remote", "get-url", "origin"], cwd=checkout)
            branch = run(["git", "branch", "--show-current"], cwd=checkout)
            if remote != PAGES_REPO or branch != PAGES_BRANCH:
                raise RuntimeError(f"Publish checkout points to {remote}#{branch}, expected {PAGES_REPO}#{PAGES_BRANCH}")
            run_with_https_fallback(["git", "fetch", PAGES_REPO, PAGES_BRANCH], cwd=checkout)
            run(["git", "merge", "--ff-only", "FETCH_HEAD"], cwd=checkout)
            return

    run_with_https_fallback([
        "git", "clone", "--depth", "1", "--branch", PAGES_BRANCH,
        "--single-branch", PAGES_REPO, WORKTREE,
    ])
    run(["git", "remote", "set-url", "origin", PAGES_REPO], cwd=checkout)


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
    if not EPISODES_FILE.exists():
        return 0
    with EPISODES_FILE.open("r", encoding="utf-8") as f:
        return len(json.load(f))


def referenced_audio_filenames() -> set[str]:
    """Return the exact audio basenames referenced by local episode metadata."""
    if not EPISODES_FILE.exists():
        return set()
    with EPISODES_FILE.open("r", encoding="utf-8") as f:
        episodes = json.load(f)
    if not isinstance(episodes, list):
        raise RuntimeError("static/episodes.json must contain a list")

    filenames: set[str] = set()
    for index, episode in enumerate(episodes, start=1):
        audio_url = episode.get("audio_url") if isinstance(episode, dict) else None
        filename = Path(unquote(urlparse(audio_url or "").path)).name
        if not filename or filename in {".", ".."}:
            raise RuntimeError(f"Episode {index} has no valid audio URL")
        filenames.add(filename)
    return filenames


def sync_referenced_audio(
    audio_src: Path,
    audio_dst: Path,
    filenames: set[str],
) -> tuple[int, int]:
    """Sync only RSS-referenced audio and remove orphaned files from the export."""
    audio_dst.mkdir(exist_ok=True)
    sources: list[Path] = []
    for filename in sorted(filenames):
        if Path(filename).name != filename:
            raise RuntimeError(f"Invalid audio filename in episode metadata: {filename}")
        source = audio_src / filename
        if not source.is_file():
            raise RuntimeError(f"RSS referenced audio is missing: {source}")
        size = source.stat().st_size
        if size > MAX_PAGES_FILE_BYTES:
            raise RuntimeError(
                f"RSS referenced audio exceeds the Cloudflare Pages limit: "
                f"{filename} ({size / 1024 / 1024:.1f} MiB)"
            )
        sources.append(source)

    removed = 0
    for existing in audio_dst.iterdir():
        if existing.is_file() and existing.name not in filenames:
            existing.unlink()
            removed += 1

    copied = 0
    for source in sources:
        destination = audio_dst / source.name
        if not destination.exists() or source.stat().st_size != destination.stat().st_size:
            shutil.copy2(source, destination)
            copied += 1
    return copied, removed


def fetch_remote_rss() -> bytes:
    request = urllib.request.Request(
        f"{PAGES_URL}/podcast.xml?publish_check={time.time_ns()}",
        headers={
            "User-Agent": HTTP_USER_AGENT,
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read()


def wait_for_remote_rss(
    expected_xml: bytes,
    *,
    timeout_seconds: int = DEPLOY_TIMEOUT_SECONDS,
    poll_interval_seconds: float = 5,
) -> None:
    """Wait until Pages serves the exact RSS generated by this publication."""
    expected_digest = hashlib.sha256(expected_xml).hexdigest()
    expected_items = len(ET.fromstring(expected_xml).findall("./channel/item"))
    deadline = time.monotonic() + timeout_seconds
    last_detail = "remote RSS was not reachable"

    while True:
        try:
            remote_xml = fetch_remote_rss()
            remote_digest = hashlib.sha256(remote_xml).hexdigest()
            remote_items = len(ET.fromstring(remote_xml).findall("./channel/item"))
            if remote_digest == expected_digest:
                print(f"Verified Cloudflare Pages deployment with {remote_items} episode(s).")
                return
            last_detail = f"remote has {remote_items} episode(s), expected {expected_items}"
        except Exception as exc:
            last_detail = str(exc)

        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Cloudflare Pages deployment was not verified within {timeout_seconds}s: {last_detail}"
            )
        time.sleep(poll_interval_seconds)


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

    prepare_worktree()

    try:
        audio_src = ROOT / "static" / "audio"
        audio_dst = Path(WORKTREE) / "audio"
        audio_dst.mkdir(exist_ok=True)
        Path(f"{WORKTREE}/.nojekyll").touch()

        # Keep the export aligned with RSS metadata. Failed jobs can leave large,
        # unreferenced media in static/audio; exporting the whole directory makes
        # Cloudflare reject an otherwise valid deployment.
        referenced_filenames = referenced_audio_filenames()
        # This Pages repository has historically hosted podcast MP3 assets only.
        # Preserve non-MP3 episode metadata without trying to upload legacy video.
        audio_filenames = {
            filename for filename in referenced_filenames
            if Path(filename).suffix.lower() == ".mp3"
        }
        copied, removed = sync_referenced_audio(audio_src, audio_dst, audio_filenames)
        print(
            f"Synced {len(audio_filenames)} referenced MP3 file(s): "
            f"copied {copied}, removed {removed} orphan(s)."
        )

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
        expected_rss = Path(f"{WORKTREE}/podcast.xml").read_bytes()

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

        print("Waiting for Cloudflare Pages to serve this RSS revision...")
        wait_for_remote_rss(expected_rss)

    finally:
        if Path(WORKTREE).exists() and not (Path(WORKTREE) / ".git").exists():
            remove_worktree()

    return f"{PAGES_URL}/podcast.xml"


if __name__ == "__main__":
    rss_url = publish()
    print(f"\nRSS URL: {rss_url}")
    print("Add this URL to Apple Podcasts or any podcast app.")
