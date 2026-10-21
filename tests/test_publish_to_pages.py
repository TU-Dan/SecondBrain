from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, call, patch

from scripts import publish_to_pages
from services import rss


class PublishToPagesTests(unittest.TestCase):
    def test_rss_build_date_is_stable_without_new_episodes(self):
        episodes = [{
            "title": "测试节目",
            "description": "测试",
            "audio_url": "https://example.com/audio/test.mp3",
            "audio_length": 5,
            "published": "2026-10-16T09:43:01+00:00",
        }]
        first = rss._build_feed("https://example.com", episodes).rss_str()
        second = rss._build_feed("https://example.com", episodes).rss_str()
        build_date = ET.fromstring(first).findtext("./channel/lastBuildDate")

        self.assertEqual(first, second)
        self.assertEqual(parsedate_to_datetime(build_date), datetime(2026, 10, 16, 9, 43, 1, tzinfo=timezone.utc))

    def test_checkout_reuses_local_clone_and_fetches_new_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            remote = Path(tmp) / "remote.git"
            checkout = Path(tmp) / "publish"
            subprocess.run(["git", "init", str(source)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(source), "checkout", "-b", "gh-pages"], check=True, capture_output=True)
            (source / "first.txt").write_text("first")
            subprocess.run(["git", "-C", str(source), "add", "first.txt"], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(source), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "first"],
                check=True, capture_output=True,
            )
            subprocess.run(["git", "clone", "--bare", str(source), str(remote)], check=True, capture_output=True)

            with (
                patch.object(publish_to_pages, "WORKTREE", str(checkout)),
                patch.object(publish_to_pages, "PAGES_REPO", str(remote)),
                patch.object(publish_to_pages, "PAGES_BRANCH", "gh-pages"),
            ):
                publish_to_pages.prepare_worktree()
                self.assertEqual((checkout / "first.txt").read_text(), "first")

                (source / "second.txt").write_text("second")
                subprocess.run(["git", "-C", str(source), "add", "second.txt"], check=True, capture_output=True)
                subprocess.run(
                    ["git", "-C", str(source), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "second"],
                    check=True, capture_output=True,
                )
                subprocess.run(["git", "-C", str(source), "push", str(remote), "gh-pages"], check=True, capture_output=True)
                publish_to_pages.prepare_worktree()
                self.assertEqual((checkout / "second.txt").read_text(), "second")

    def test_existing_checkout_fetches_instead_of_cloning(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkout = Path(tmp) / "publish"
            (checkout / ".git").mkdir(parents=True)
            commands = Mock(side_effect=["commit", publish_to_pages.PAGES_REPO, publish_to_pages.PAGES_BRANCH, ""])

            with (
                patch.object(publish_to_pages, "WORKTREE", str(checkout)),
                patch.object(publish_to_pages, "run", commands),
                patch.object(publish_to_pages, "run_with_https_fallback") as fetch,
            ):
                publish_to_pages.prepare_worktree()

            fetch.assert_called_once_with(
                ["git", "fetch", publish_to_pages.PAGES_REPO, publish_to_pages.PAGES_BRANCH],
                cwd=checkout,
            )
            self.assertEqual(commands.call_args, call(["git", "merge", "--ff-only", "FETCH_HEAD"], cwd=checkout))

    def test_missing_checkout_clones_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkout = Path(tmp) / "publish"
            with (
                patch.object(publish_to_pages, "WORKTREE", str(checkout)),
                patch.object(publish_to_pages, "run") as run,
                patch.object(publish_to_pages, "run_with_https_fallback") as clone,
            ):
                publish_to_pages.prepare_worktree()

            clone.assert_called_once()
            self.assertEqual(clone.call_args.args[0][1], "clone")
            run.assert_called_once_with(["git", "remote", "set-url", "origin", publish_to_pages.PAGES_REPO], cwd=checkout)

    def test_sync_audio_copies_only_rss_references_and_removes_orphans(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            destination.mkdir()
            (source / "current.mp3").write_bytes(b"current")
            (source / "orphan.mp3").write_bytes(b"orphan")
            (destination / "old-orphan.mp3").write_bytes(b"old")

            copied, removed = publish_to_pages.sync_referenced_audio(
                source,
                destination,
                {"current.mp3"},
            )

            self.assertEqual(copied, 1)
            self.assertEqual(removed, 1)
            self.assertEqual(
                sorted(path.name for path in destination.iterdir()),
                ["current.mp3"],
            )

    def test_referenced_audio_filenames_come_from_episode_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            episodes_file = Path(tmp) / "episodes.json"
            episodes_file.write_text(
                json.dumps([
                    {"audio_url": "http://localhost/static/audio/one.mp3"},
                    {"audio_url": "https://example.com/audio/two.mp3?token=test"},
                ]),
                encoding="utf-8",
            )

            with patch.object(publish_to_pages, "EPISODES_FILE", episodes_file):
                filenames = publish_to_pages.referenced_audio_filenames()

            self.assertEqual(filenames, {"one.mp3", "two.mp3"})

    def test_sync_audio_rejects_oversized_referenced_file_before_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            destination.mkdir()
            audio = source / "oversized.mp3"
            audio.write_bytes(b"x")

            with (
                patch.object(publish_to_pages, "MAX_PAGES_FILE_BYTES", 0),
                self.assertRaisesRegex(RuntimeError, "Cloudflare Pages"),
            ):
                publish_to_pages.sync_referenced_audio(
                    source,
                    destination,
                    {audio.name},
                )

    def test_wait_for_remote_rss_does_not_report_success_before_deployment(self):
        expected = b"<rss><channel><item /></channel></rss>"
        with (
            patch.object(
                publish_to_pages,
                "fetch_remote_rss",
                side_effect=[b"<rss><channel /></rss>", expected],
            ) as fetch,
            patch.object(publish_to_pages.time, "sleep"),
        ):
            publish_to_pages.wait_for_remote_rss(
                expected,
                timeout_seconds=1,
                poll_interval_seconds=0,
            )

        self.assertEqual(fetch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
