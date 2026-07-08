"""
월간 Wrapped 배치 실행 스크립트.

매월 마지막 영업일에 전월 Wrapped를 생성·발송합니다.
Task Scheduler / cron 등록용.

사용 예:
  python scripts/run_monthly_wrapped.py
  python scripts/run_monthly_wrapped.py --email
  python scripts/run_monthly_wrapped.py --force   # 날짜 무시 (테스트)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from services.wrapped_delivery import WrappedDelivery  # noqa: E402
from utils.console_encoding import configure_utf8_console  # noqa: E402
from utils.errors import FoodFinderError  # noqa: E402
from utils.logger import setup_logging  # noqa: E402

configure_utf8_console()


def main() -> int:
    parser = argparse.ArgumentParser(description="월간 맛집 Wrapped 배치")
    parser.add_argument("--email", action="store_true", help="SMTP 이메일 발송")
    parser.add_argument("--force", action="store_true", help="영업일 조건 무시")
    parser.add_argument(
        "--diary",
        default="data/diary/default.json",
        help="식사 기록 JSON 경로",
    )
    parser.add_argument(
        "--places",
        default="site/data/places.json",
        help="맛집 카탈로그 JSON 경로",
    )
    args = parser.parse_args()

    setup_logging()
    try:
        delivery = WrappedDelivery.from_paths(args.diary, args.places)
        report = delivery.run_monthly(use_email=args.email, force=args.force)
        if report is None:
            print("배치 조건 미충족 — 스킵됨 (월말 영업일이 아님)")
            return 0
        return 0
    except FoodFinderError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
