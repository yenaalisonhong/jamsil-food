"""로컬 사이트 스모크 테스트 (기본 http://localhost:8765)."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 8765
CHECK_PATHS = (
    "/api/health",
    "/",
    "/index.html",
    "/js/app.js",
    "/css/style.css",
    "/data/places.json",
    "/api/config",
    "/diary.html",
    "/diary-day.html",
    "/diary-picks.html",
    "/js/diary-shared.js",
    "/js/diary.js",
    "/js/diary-day.js",
    "/js/diary-picks.js",
    "/js/wrapped-shared.js",
    "/js/wrapped.js",
)


def probe(path: str, port: int, timeout: float) -> str | None:
    url = f"http://localhost:{port}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as res:
            if res.status != 200:
                return f"{res.status} {path}"
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code} {path}"
    except Exception as exc:
        return f"{path}: {exc}"
    return None


def server_up(port: int) -> bool:
    return probe("/", port, timeout=2.0) is None


def start_server(port: int) -> None:
    if server_up(port):
        return
    subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "serve_site.py"), "--port", str(port)],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    for _ in range(30):
        if server_up(port):
            return
        time.sleep(0.5)
    raise RuntimeError(f"server did not start on port {port}")


def main() -> int:
    parser = argparse.ArgumentParser(description="잠실맛집 로컬 사이트 연결 확인")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument(
        "--start",
        action="store_true",
        help="서버가 꺼져 있으면 자동 시작",
    )
    args = parser.parse_args()

    base = f"http://localhost:{args.port}"
    if not server_up(args.port):
        if not args.start:
            print(f"Site check failed ({base}):")
            print("  - server not running")
            print(f"\n서버 시작: python scripts/serve_site.py --port {args.port}")
            print(f"또는: python scripts/verify_site.py --start")
            return 1
        print(f"Starting server on {base} ...")
        start_server(args.port)

    failures: list[str] = []
    for path in CHECK_PATHS:
        err = probe(path, args.port, args.timeout)
        if err:
            failures.append(err)

    if failures:
        print(f"Site check failed ({base}):")
        for item in failures:
            print(f"  - {item}")
        print(f"\n서버 재시작: python scripts/serve_site.py --port {args.port}")
        return 1

    print(f"OK - {len(CHECK_PATHS)} pages/assets on {base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
