"""잠실맛집 웹 UI 로컬 서버 (정적 파일 + /api/places)."""

from __future__ import annotations

import argparse
import json
import socketserver
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_CLIENT_GONE = (ConnectionAbortedError, BrokenPipeError, ConnectionResetError)


class SiteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE_DIR), **kwargs)

    def handle(self) -> None:
        try:
            super().handle()
        except _CLIENT_GONE:
            pass

    def end_headers(self) -> None:
        path = urlparse(self.path).path.lower()
        if path.endswith((".html", ".js", ".css")) or path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json({"ok": True})
            return
        if parsed.path == "/api/places":
            self._serve_api_places()
            return
        if parsed.path == "/api/config":
            self._serve_api_config()
            return
        super().do_GET()

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except _CLIENT_GONE:
            pass

    def _serve_api_places(self) -> None:
        try:
            scripts_dir = str(ROOT / "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            from export_places import build_payload, collect_places

            places = collect_places(use_mock=False, enable_crawl=True)
            self._send_json(build_payload(places))
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def _serve_api_config(self) -> None:
        try:
            from config.settings import get_settings

            settings = get_settings()
            self._send_json(
                {
                    "office_lat": settings.fraunhofer_office_lat,
                    "office_lng": settings.fraunhofer_office_lng,
                    "kakao_js_key": settings.kakao_rest_api_key,
                },
            )
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def log_message(self, format: str, *args) -> None:
        if "/api/" not in (args[0] if args else ""):
            super().log_message(format, *args)


def main() -> None:
    parser = argparse.ArgumentParser(description="잠실맛집 site/ 로컬 서버")
    parser.add_argument("--port", type=int, default=8765, help="포트 (기본 8765)")
    parser.add_argument("--open", action="store_true", help="브라우저 자동 열기")
    args = parser.parse_args()

    class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True
        daemon_threads = True

    with ReusableTCPServer(("", args.port), SiteHandler) as httpd:
        url = f"http://localhost:{args.port}"
        print(f"잠실맛집 사이트: {url}")
        print("API: /api/places · /api/config")
        print("종료: Ctrl+C")
        if args.open:
            webbrowser.open(url)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
