from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class FakeRequest:
    def __init__(self, body: dict):
        self.body = body

    async def json(self) -> dict:
        return self.body


class ArticleContentSaveTests(unittest.TestCase):
    def test_first_save_creates_markdown_for_fallback_article(self):
        article_id = "961d08df531d4628a5165cdf1669b8b3"
        article = {
            "id": article_id,
            "title": "鲁豫对话罗翔",
            "article_md_path": None,
        }
        content = "# 鲁豫对话罗翔\n\n这是编辑后保存的正文。"

        with tempfile.TemporaryDirectory() as tmp:
            scripts_dir = Path(tmp) / "scripts"
            with (
                patch("services.db.get_article", return_value=article),
                patch("services.db.update_article_content_path") as update_path,
                patch.object(main, "ARTICLE_SCRIPTS_DIR", scripts_dir, create=True),
            ):
                response = asyncio.run(
                    main.save_article_content(
                        article_id,
                        FakeRequest({"content": content}),
                    )
                )

            payload = json.loads(response.body)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["created"])
            created_files = list(scripts_dir.glob("*.md"))
            self.assertEqual(len(created_files), 1)
            self.assertEqual(created_files[0].read_text(encoding="utf-8"), content)
            update_path.assert_called_once_with(
                article_id,
                f"/static/scripts/{created_files[0].name}",
                len(content),
            )

    def test_save_keeps_existing_markdown_path(self):
        article_id = "existing-article"
        content = "# 已有文章\n\n更新后的正文。"
        with tempfile.TemporaryDirectory(dir=".") as tmp:
            file_path = Path(tmp) / "existing.md"
            file_path.write_text("旧正文", encoding="utf-8")
            public_path = f"/{file_path.as_posix().removeprefix('./')}"
            article = {
                "id": article_id,
                "title": "已有文章",
                "article_md_path": public_path,
            }

            with (
                patch("services.db.get_article", return_value=article),
                patch("services.db.update_article_content_path") as update_path,
            ):
                response = asyncio.run(
                    main.save_article_content(
                        article_id,
                        FakeRequest({"content": content}),
                    )
                )

            payload = json.loads(response.body)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(payload["created"])
            self.assertEqual(file_path.read_text(encoding="utf-8"), content)
            update_path.assert_not_called()


if __name__ == "__main__":
    unittest.main()
