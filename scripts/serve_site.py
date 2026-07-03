"""잠실맛집 정적 사이트를 로컬에서 띄웁니다 (네이버 API 서비스 URL 확인용)."""

from __future__ import annotations

import argparse
import http.server
import socketserver
import webbrowser
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent.parent / "site"


def main() -> None:
    parser = argparse.ArgumentParser(description="잠실맛집 site/ 로컬 서버")
    parser.add_argument("--port", type=int, default=8080, help="포트 (기본 8080)")
    parser.add_argument("--open", action="store_true", help="브라우저 자동 열기")
    args = parser.parse_args()

    class SiteHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(SITE_DIR), **kwargs)

    with socketserver.TCPServer(("", args.port), SiteHandler) as httpd:
        url = f"http://localhost:{args.port}"
        print(f"잠실맛집 사이트: {url}")
        print("네이버 개발자센터 서비스 URL에 위 주소를 입력하세요.")
        print("종료: Ctrl+C")
        if args.open:
            webbrowser.open(url)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
