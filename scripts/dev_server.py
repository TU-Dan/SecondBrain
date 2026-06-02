#!/usr/bin/env python3
"""Start the SecondBrain dev server with a small health check.

This wraps the repeated local workflow:
1. stop an existing uvicorn process on the configured port;
2. start the app;
3. wait until the HTTP endpoint responds.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_LOG = ROOT / "data" / "dev_server.log"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start or restart the local SecondBrain server.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--reload", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--no-stop", action="store_true", help="Do not stop an existing process first.")
    parser.add_argument("--log", default=str(DEFAULT_LOG), help="Where server logs should be written.")
    parser.add_argument("--timeout", type=float, default=90.0, help="Seconds to wait for HTTP startup.")
    parser.add_argument("--foreground", action="store_true", help="Run uvicorn in the foreground.")
    return parser.parse_args()


def find_pids_on_port(port: int) -> list[int]:
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []
    pids = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return sorted(set(pids))


def stop_pid(pid: int) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except PermissionError:
        print(f"Could not stop pid {pid}: permission denied.")
        return False
    deadline = time.time() + 6
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except PermissionError:
        print(f"Could not force-stop pid {pid}: permission denied.")
        return False
    return True


def wait_for_http(url: str, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return 200 <= response.status < 500
        except Exception:
            time.sleep(0.5)
    return False


def tail_log(path: Path, lines: int = 40) -> str:
    if not path.exists():
        return ""
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except Exception:
        return ""


def main() -> int:
    args = parse_args()
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if not args.no_stop:
        pids = find_pids_on_port(args.port)
        if pids:
            print(f"Stopping existing server on port {args.port} (pid(s) {', '.join(map(str, pids))})...")
        for pid in pids:
            if not stop_pid(pid):
                print("Stop the existing server manually, then run this command again:")
                print(f"  kill {' '.join(map(str, pids))}")
                return 1

    cmd = [sys.executable, "-m", "uvicorn", "main:app", "--host", args.host, "--port", str(args.port)]
    if args.reload:
        cmd.append("--reload")

    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(ROOT))

    log_file = log_path.open("a", encoding="utf-8")
    log_file.write(f"\n\n--- starting {' '.join(cmd)} at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    log_file.flush()

    if args.foreground:
        log_file.close()
        print(f"Running: {' '.join(cmd)}")
        print("Press Ctrl+C to stop.")
        return subprocess.run(cmd, cwd=ROOT, env=env).returncode

    subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
    )

    url = f"http://{args.host}:{args.port}/"
    if not wait_for_http(url, args.timeout):
        print(f"Server did not pass HTTP health check within {args.timeout:.0f}s. See {log_path}")
        recent = tail_log(log_path)
        if recent:
            print("\nRecent server log:")
            print(recent)
        return 1

    print(f"SecondBrain is running: {url}")
    print(f"Logs: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
