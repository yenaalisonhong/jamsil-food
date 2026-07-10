"""잠실맛집 웹 UI 로컬 서버 (정적 파일 + /api/places · /api/diary)."""

from __future__ import annotations

import argparse
import json
import re
import socketserver
import sys
import webbrowser
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
DOCS_DIR = ROOT / "docs"
DIARY_PATHS = (
    SITE_DIR / "data" / "diary.json",
    DOCS_DIR / "data" / "diary.json",
    ROOT / "data" / "diary" / "default.json",
)
_DATE_KEY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_CLIENT_GONE = (ConnectionAbortedError, BrokenPipeError, ConnectionResetError)


def _normalize_diary(payload: dict[str, Any]) -> dict[str, Any]:
    updated_at = payload.get("_updatedAt") or payload.get("updatedAt")
    if not isinstance(updated_at, str) or not updated_at.strip():
        updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    out: dict[str, Any] = {"_updatedAt": updated_at}
    for key, value in payload.items():
        if not _DATE_KEY_RE.match(key) or not isinstance(value, list):
            continue
        rows: list[dict[str, Any]] = []
        for entry in value:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            rating_raw = entry.get("rating", 4)
            try:
                rating = max(1, min(5, round(float(rating_raw))))
            except (TypeError, ValueError):
                rating = 4
            row: dict[str, Any] = {
                "name": name,
                "rating": rating,
                "memo": str(entry.get("memo", "") or "").strip(),
                "createdAt": (
                    entry.get("createdAt")
                    if isinstance(entry.get("createdAt"), str)
                    else datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                ),
            }
            place_id = entry.get("place_id") or entry.get("placeId")
            if isinstance(place_id, str) and place_id.strip():
                row["place_id"] = place_id.strip()
            for price_key in ("price_min_krw", "price_max_krw"):
                raw_price = entry.get(price_key)
                if raw_price is None or raw_price == "":
                    continue
                try:
                    row[price_key] = max(0, round(float(raw_price)))
                except (TypeError, ValueError):
                    pass
            if "price_min_krw" in row and "price_max_krw" in row:
                lo, hi = row["price_min_krw"], row["price_max_krw"]
                if lo > hi:
                    row["price_min_krw"], row["price_max_krw"] = hi, lo
            elif "price_min_krw" in row:
                row["price_max_krw"] = row["price_min_krw"]
            elif "price_max_krw" in row:
                row["price_min_krw"] = row["price_max_krw"]
            rows.append(row)
        if rows:
            out[key] = rows
    return out


def _read_diary() -> dict[str, Any]:
    for path in DIARY_PATHS:
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(raw, dict):
            return _normalize_diary(raw)
    return _normalize_diary({})


def _write_diary(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_diary(payload)
    text = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"
    for path in DIARY_PATHS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return normalized


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

    def do_OPTIONS(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            return
        self.send_error(404)

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
        if parsed.path == "/api/diary":
            self._send_json(_read_diary())
            return
        super().do_GET()

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/diary":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw_body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._send_json({"error": f"invalid json: {exc}"}, status=400)
            return
        if not isinstance(payload, dict):
            self._send_json({"error": "diary payload must be an object"}, status=400)
            return
        try:
            saved = _write_diary(payload)
        except OSError as exc:
            self._send_json({"error": str(exc)}, status=500)
            return
        self._send_json(saved)

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
        print("API: /api/places · /api/config · /api/diary")
        print("종료: Ctrl+C")
        if args.open:
            webbrowser.open(url)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
