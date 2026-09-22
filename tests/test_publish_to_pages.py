from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import publish_to_pages


class PublishToPagesTests(unittest.TestCase):
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
