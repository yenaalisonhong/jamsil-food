"""하위 호환 — supplement_near_commercial.py 사용."""

from scripts.supplement_near_commercial import supplement_near_commercial

supplement_jangmi = supplement_near_commercial

if __name__ == "__main__":
    import argparse

    from providers.jamsil_commercial import NEAREST_COMMERCIAL_COUNT

    parser = argparse.ArgumentParser(
        description=f"가장 가까운 {NEAREST_COMMERCIAL_COUNT}개 상가 심층 보충 수집",
    )
    parser.add_argument("--no-crawl", action="store_true")
    parser.add_argument("--delay", type=float, default=8.0)
    args = parser.parse_args()
    count = supplement_near_commercial(
        enable_crawl=not args.no_crawl,
        request_delay_sec=args.delay,
    )
    print(f"Done. Added {count} places.")
