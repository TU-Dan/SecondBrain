from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from services import tts


class TtsTimeoutTests(unittest.TestCase):
    def test_stalled_stream_fails_before_stage_timeout_and_cleans_partial_audio(self):
        class StalledSpeech:
            async def save(self, path):
                Path(path).write_bytes(b"partial audio")
                await asyncio.Event().wait()

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(tts.edge_tts, "Communicate", return_value=StalledSpeech()),
                patch.object(tts, "TTS_REQUEST_TIMEOUT_SECONDS", 0.01, create=True),
                patch.object(tts.asyncio, "sleep", new_callable=AsyncMock),
            ):
                with self.assertRaisesRegex(RuntimeError, "超时"):
                    asyncio.run(asyncio.wait_for(tts.generate_audio("测试语音。", output_dir=tmp), 0.5))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_later_chunk_failure_does_not_publish_incomplete_audio(self):
        class Forbidden(Exception):
            status = 403

        class Speech:
            calls = 0

            async def save(self, path):
                self.calls += 1
                if self.calls >= 2:
                    raise Forbidden("service unavailable")
                Path(path).write_bytes(b"audio")

        speech = Speech()
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(tts, "_split_for_tts", return_value=["第一段。", "第二段。"]),
                patch.object(tts.edge_tts, "Communicate", return_value=speech),
                patch.object(tts.asyncio, "sleep", new_callable=AsyncMock),
            ):
                with self.assertRaisesRegex(RuntimeError, "403"):
                    asyncio.run(tts.generate_audio("第一段。第二段。", output_dir=tmp))
            self.assertEqual(list(Path(tmp).iterdir()), [])
