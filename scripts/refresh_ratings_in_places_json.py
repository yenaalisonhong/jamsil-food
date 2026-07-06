"""places.json 평점·리뷰를 캐시·네이버에서 보강합니다."""

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


def _needs_refresh(raw: dict) -> bool:
    return raw.get("rating") is None


def _needs_review_backfill(raw: dict) -> bool:
    return raw.get("rating") is None and not _has_review(raw)


def _apply_cached(raw: dict, cached: dict) -> bool:
    changed = False
    if raw.get("rating") is None and cached.get("rating"):
        raw["rating"] = cached["rating"]
        raw["rating_source"] = "naver_crawl"
        changed = True
    if raw.get("review_count") is None and cached.get("review_count") is not None:
        raw["review_count"] = cached["review_count"]
        changed = True
    if not _has_review(raw) and cached.get("representative_review"):
        raw["representative_review"] = cached["representative_review"]
        reviews = list(cached.get("representative_reviews") or [])
        if reviews:
            raw["representative_reviews"] = reviews[:2]
        changed = True
    return changed


def _save_data(path: Path, data: dict) -> None:
    from scripts.reclassify_places import _atomic_write_json, finalize_places_data

    finalize_places_data(data)
    _atomic_write_json(path, data)


def refresh(
    path: Path,
    *,
    crawl: bool = False,
    crawl_limit: int | None = None,
    save_every: int = 10,
    request_delay_sec: float = 12.0,
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
    places = data.get("places", [])

    for index, raw in enumerate(places, start=1):
        if not _needs_refresh(raw) and _has_review(raw):
            continue

        naver_id = _naver_id(raw)
        if naver_id:
            entry = cache.get(naver_id)
            cached = entry.get("data", {}) if entry else {}
            if cached and _apply_cached(raw, cached):
                cache_updates += 1
                if raw.get("rating") is not None and _has_review(raw):
                    continue

            if crawl and crawler:
                if crawl_limit is not None and crawl_attempts >= crawl_limit:
                    break
                if not (raw.get("rating") is not None and _has_review(raw)):
                    place_type = PlaceType(raw.get("place_type", "restaurant"))
                    detail = crawler.fetch_detail(naver_id, place_type, light=True)
                    crawl_attempts += 1
                    changed = False
                    if raw.get("rating") is None and detail.rating is not None and detail.rating > 0:
                        raw["rating"] = detail.rating
                        raw["rating_source"] = "naver_crawl"
                        changed = True
                    if raw.get("review_count") is None and detail.review_count is not None:
                        raw["review_count"] = detail.review_count
                        changed = True
                    if not _has_review(raw) and detail.representative_review:
                        _apply_review(
                            raw,
                            detail.representative_review,
                            detail.representative_reviews,
                        )
                        changed = True
                    if changed:
                        crawl_updates += 1
                    if crawl_attempts % save_every == 0:
                        _save_data(path, data)

        if _needs_review_backfill(raw) and blog_fetcher:
            if _try_blog_review(blog_fetcher, raw):
                blog_updates += 1
            if blog_delay_sec > 0:
                time.sleep(blog_delay_sec)

    _save_data(path, data)
    rated = sum(1 for p in places if p.get("rating") is not None)
    with_review = sum(1 for p in places if _has_review(p))
    print(
        f"{path.name}: cache={cache_updates}, crawl={crawl_updates}, blog={blog_updates}, "
        f"rated={rated}/{len(places)}, with_review={with_review}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="places.json 평점·리뷰 보강")
    parser.add_argument("--crawl", action="store_true", help="캐시에 없으면 네이버 조회")
    parser.add_argument("--crawl-limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=12.0)
    parser.add_argument("--blog-delay", type=float, default=1.0)
    parser.add_argument(
        "--path",
        type=Path,
        default=ROOT / "site" / "data" / "places.json",
    )
    args = parser.parse_args()

    refresh(
        args.path,
        crawl=args.crawl,
        crawl_limit=args.crawl_limit,
        request_delay_sec=args.delay,
        blog_delay_sec=args.blog_delay,
    )

    docs_path = ROOT / "docs" / "data" / "places.json"
    if docs_path != args.path and docs_path.exists():
        refresh(docs_path, crawl=False)


if __name__ == "__main__":
    main()
