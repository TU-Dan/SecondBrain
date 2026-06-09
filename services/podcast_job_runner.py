from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "packages" / "content-to-podcast"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PACKAGE_ROOT))

from services import podcast_jobs


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m services.podcast_job_runner JOB_ID")
        return 2
    result = podcast_jobs._run(sys.argv[1])
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
