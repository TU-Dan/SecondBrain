"""Consistent SQLite snapshot plus article files for the edit-only website."""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=Path("backups/knowledge-web"))
    parser.add_argument("--keep", type=int, default=14)
    args = parser.parse_args()
    if args.keep < 1:
        parser.error("--keep must be at least 1")

    source = Path("data/knowledge.db")
    if not source.is_file():
        parser.error(f"database missing: {source}")
    args.destination.mkdir(parents=True, exist_ok=True)
    os.chmod(args.destination, 0o700)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive = args.destination / f"knowledge-web-{timestamp}.tar.gz"
    temporary_archive = archive.with_suffix(".tmp")
    try:
        with tempfile.TemporaryDirectory(prefix="knowledge-backup-") as temporary:
            snapshot = Path(temporary)
            (snapshot / "data").mkdir()
            (snapshot / "static").mkdir()
            with sqlite3.connect(source) as original, sqlite3.connect(snapshot / "data/knowledge.db") as target:
                original.backup(target)
            for directory in (Path("static/scripts"), Path("static/images")):
                if directory.is_dir():
                    shutil.copytree(directory, snapshot / directory)
            with tarfile.open(temporary_archive, "w:gz") as tar:
                tar.add(snapshot / "data", arcname="data")
                tar.add(snapshot / "static", arcname="static")
        os.chmod(temporary_archive, 0o600)
        os.replace(temporary_archive, archive)
    finally:
        temporary_archive.unlink(missing_ok=True)

    older = sorted(args.destination.glob("knowledge-web-*.tar.gz"), reverse=True)
    for file in older[args.keep:]:
        file.unlink()
    print(f"backup ok: {archive}")


if __name__ == "__main__":
    main()
