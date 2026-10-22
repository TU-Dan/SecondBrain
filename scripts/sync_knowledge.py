#!/usr/bin/env python3
"""Preview or apply the local-to-web knowledge library sync."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.knowledge_sync import SyncError, synchronize


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply safe changes; leave conflicts untouched")
    parser.add_argument("--bootstrap-server", action="store_true", help="On first sync, back up divergent local copies and accept the server version")
    parser.add_argument("--json", action="store_true", help="Print the full machine-readable report")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    try:
        if args.bootstrap_server and not args.apply:
            parser.error("--bootstrap-server requires --apply")
        result = synchronize(apply=args.apply, accept_server_for_initial_conflicts=args.bootstrap_server)
    except SyncError as error:
        print(f"同步失败：{error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"mode": "apply" if args.apply else "preview", **result}, ensure_ascii=False, indent=2))
    else:
        names = {"new": "新增", "pull": "网页→本地", "push": "本地→网页", "conflicts": "冲突", "same": "一致", "errors": "错误"}
        print("已执行同步" if args.apply else "同步预览")
        for key, label in names.items():
            print(f"{label}：{len(result[key])}")
        for article_id in result["conflicts"]:
            print(f"需处理冲突：{article_id}")
        for item in result["errors"]:
            print(f"同步错误：{item['id']} — {item['error']}")
    return 2 if result["conflicts"] or result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
