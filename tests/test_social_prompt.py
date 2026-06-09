from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.llm import _build_social_post_prompt


class SocialPromptTests(unittest.TestCase):
    def test_wechat_prompt_avoids_preaching_style(self):
        prompt, max_tokens, system_prompt = _build_social_post_prompt(
            "这是一篇关于工作、注意力和选择的文章。" * 50,
            "wechat",
            "",
        )

        self.assertEqual(max_tokens, 3600)
        self.assertIn("能看见作者思考过程", prompt)
        self.assertIn("不要批评读者", prompt)
        self.assertIn("不要输出行动清单", prompt)
        self.assertIn("核心主张是什么", prompt)
        self.assertIn("主调选择（选一个", prompt)
        self.assertIn("叙事视角（选一个", prompt)
        self.assertIn("结尾基调（选一个", prompt)
        self.assertIn("每一个转折都要有过渡", prompt)
        self.assertIn("每一段的第一句要能独立成立", prompt)
        self.assertIn("核心张力", prompt)
        self.assertIn("最强素材", prompt)
        self.assertIn("具体代价", prompt)
        self.assertIn("意外事实", prompt)
        self.assertIn("前 120 字", prompt)
        self.assertIn("【改稿诊断】", prompt)
        self.assertIn("【改后全文】", prompt)
        self.assertIn("不要训诫读者", system_prompt)
        self.assertIn("编辑判断力", system_prompt)
        self.assertIn("严格输出【改稿诊断】和【改后全文】", system_prompt)
        self.assertNotIn("Dan Koe", prompt)
        self.assertNotIn("给出行动路径", prompt)
        self.assertNotIn("让读者意识到", prompt)

    def test_other_social_formats_keep_original_positioning(self):
        prompt, _, system_prompt = _build_social_post_prompt("文章内容", "list", "")

        self.assertIn("清单体短内容", prompt)
        self.assertIn("中文社媒内容主笔", system_prompt)


if __name__ == "__main__":
    unittest.main()
