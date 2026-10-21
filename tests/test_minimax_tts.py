from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import tts


class MiniMaxTtsTests(unittest.TestCase):
    def test_selected_voice_calls_minimax_and_saves_audio(self):
        response = io.BytesIO(json.dumps({
            "base_resp": {"status_code": 0},
            "data": {"audio": b"mp3-data".hex()},
        }).encode())
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}),
                patch.object(tts.urllib.request, "urlopen", return_value=response) as urlopen,
                patch.object(tts.edge_tts, "Communicate") as edge,
            ):
                filename = tts.generate_audio_sync("你好。", "minimax:Chinese (Mandarin)_Gentleman", tmp)
            self.assertEqual((Path(tmp) / filename).read_bytes(), b"mp3-data")
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload["voice_setting"]["voice_id"], "Chinese (Mandarin)_Gentleman")
        edge.assert_not_called()

    def test_minimax_failure_removes_partial_audio(self):
        responses = [
            io.BytesIO(json.dumps({"base_resp": {"status_code": 0}, "data": {"audio": "aabb"}}).encode()),
            io.BytesIO(json.dumps({"base_resp": {"status_code": 1002, "status_msg": "rate limit"}}).encode()),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}),
                patch.object(tts, "_split_for_tts", return_value=["第一段。", "第二段。"]),
                patch.object(tts.urllib.request, "urlopen", side_effect=responses),
            ):
                with self.assertRaisesRegex(RuntimeError, "1002"):
                    tts.generate_audio_sync("第一段。第二段。", "minimax:Chinese (Mandarin)_Gentleman", tmp)
            self.assertEqual(list(Path(tmp).iterdir()), [])
