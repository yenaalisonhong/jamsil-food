"""places.json에 캐시·크롤로 대표 리뷰를 보강합니다."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import get_settings  # noqa: E402
from models.place import PlaceType  # noqa: E402
from services.manual_data_store import ManualDataStore  # noqa: E402
from services.naver_blog_review import NaverBlogReviewFetcher  # noqa: E402
from services.naver_place_crawler import NaverPlaceCrawler  # noqa: E402
from utils.errors import ConfigurationError  # noqa: E402
from utils.naver_urls import extract_naver_place_id  # noqa: E402


def _naver_id(raw: dict) -> str | None:
    from_url = extract_naver_place_id(str(raw.get("url") or ""))
    if from_url:
        return from_url
    place_id = str(raw.get("id") or "")
    if place_id.startswith("naver:"):
        candidate = place_id.split(":", 1)[1]
        if candidate.isdigit():
            return candidate
    return None


def _has_review(raw: dict) -> bool:
    if raw.get("representative_review"):
        return True
    return bool([r for r in (raw.get("representative_reviews") or []) if r])


def _needs_review(raw: dict) -> bool:
    if raw.get("rating") is not None:
        return False
    return not _has_review(raw)


def _apply_review(raw: dict, review: str, reviews: list[str] | None = None) -> None:
    raw["representative_review"] = review
    merged = list(reviews or [])
    if review and review not in merged:
        merged.insert(0, review)
    if merged:
        raw["representative_reviews"] = merged[:2]


def _try_blog_review(blog_fetcher: NaverBlogReviewFetcher | None, raw: dict) -> bool:
    if not blog_fetcher:
        return False
    name = str(raw.get("name") or "").strip()
    if not name:
        return False
    snippet = blog_fetcher.fetch_review_snippet(name)
    if not snippet:
        return False
    _apply_review(raw, snippet)
    return True


def _save_data(path: Path, data: dict) -> None:
    from scripts.reclassify_places import _atomic_write_json, finalize_places_data

    finalize_places_data(data)
    _atomic_write_json(path, data)


def backfill(
    path: Path,
    *,
    crawl: bool = False,
    crawl_limit: int | None = None,
    request_delay_sec: float = 8.0,
    blog_delay_sec: float = 1.0,
) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    store = ManualDataStore()
    cache = store._load_json(store._cache_path)
    crawler = (
        NaverPlaceCrawler(store, request_delay_sec=request_delay_sec) if crawl else None
    )
    blog_fetcher: NaverBlogReviewFetcher | None = None
    try:
        blog_fetcher = NaverBlogReviewFetcher(get_settings())
    except ConfigurationError:
        blog_fetcher = None

    cache_updates = 0
    crawl_updates = 0
    blog_updates = 0
    crawl_attempts = 0
    blog_attempts = 0
    places = data.get("places", [])

    for raw in places:
        if not _needs_review(raw):
            continue

        naver_id = _naver_id(raw)
        if naver_id:
            entry = cache.get(naver_id)
            cached = entry.get("data", {}) if entry else {}
            review = cached.get("representative_review")
            reviews = list(cached.get("representative_reviews") or [])
            if review:
                _apply_review(raw, review, reviews)
                cache_updates += 1
                continue

            if crawl and crawler:
                if crawl_limit is None or crawl_attempts < crawl_limit:
                    place_type = PlaceType(raw.get("place_type", "restaurant"))
                    detail = crawler.fetch_detail(naver_id, place_type, light=True)
                    crawl_attempts += 1
                    if detail.representative_review:
                        _apply_review(
                            raw,
                            detail.representative_review,
                            detail.representative_reviews,
                        )
                        crawl_updates += 1
                        if crawl_attempts % 10 == 0:
                            _save_data(path, data)
                        continue

        if not _needs_review(raw):
            continue

        if blog_fetcher:
            blog_attempts += 1
            if _try_blog_review(blog_fetcher, raw):
                blog_updates += 1
            if blog_delay_sec > 0:
                time.sleep(blog_delay_sec)

    _save_data(path, data)
    with_review = sum(
        1
        for p in places
        if p.get("rating") is None and _has_review(p)
    )
    print(
        f"{path.name}: cache={cache_updates}, crawl={crawl_updates}, blog={blog_updates}, "
        f"no_rating_with_review={with_review}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="places.json 대표 리뷰 보강")
    parser.add_argument("--crawl", action="store_true", help="캐시에 없으면 네이버 리뷰 조회")
    parser.add_argument("--crawl-limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--blog-delay", type=float, default=1.0)
    parser.add_argument(
        "--path",
        type=Path,
        default=ROOT / "site" / "data" / "places.json",
    )
    args = parser.parse_args()

    backfill(
        args.path,
        crawl=args.crawl,
        crawl_limit=args.crawl_limit,
        request_delay_sec=args.delay,
        blog_delay_sec=args.blog_delay,
    )

    docs_path = ROOT / "docs" / "data" / "places.json"
    if docs_path != args.path and docs_path.exists():
        backfill(docs_path, crawl=False)


if __name__ == "__main__":
    main()
