"""
수동 보강 데이터 저장소.

API·크롤링으로 얻기 어려운 인당 가격, 개업일을 JSON 파일로 관리합니다.
"""

import json
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from config.settings import Settings, get_settings
from utils.logger import get_logger

logger = get_logger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _normalize_key(name: str) -> str:
    """상호명 매칭용 정규화."""
    return re.sub(r"\s+", "", name.lower())


class ManualDataStore:
    """manual_prices.json / manual_openings.json 읽기·쓰기."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or _DATA_DIR
        self._prices_path = self._data_dir / "manual_prices.json"
        self._openings_path = self._data_dir / "manual_openings.json"
        self._cache_path = self._data_dir / "cache" / "place_details.json"

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        for attempt in range(4):
            try:
                raw = path.read_text(encoding="utf-8").strip()
                if not raw:
                    return {}
                data = json.loads(raw)
                return {k: v for k, v in data.items() if not k.startswith("_")}
            except json.JSONDecodeError:
                logger.warning("JSON 손상/비어 있음 — 초기화: %s", path)
                return {}
            except OSError as exc:
                if attempt < 3:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                logger.warning("JSON 읽기 실패 — 건너뜀: %s (%s)", path, exc)
                return {}
        return {}

    def _save_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(data, ensure_ascii=False, indent=2)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        for attempt in range(3):
            try:
                tmp.replace(path)
                return
            except OSError as exc:
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                logger.warning("캐시 replace 실패, 직접 저장 시도: %s", exc)
        path.write_text(content, encoding="utf-8")
        tmp.unlink(missing_ok=True)

    def get_price(
        self,
        *,
        place_id: str | None = None,
        naver_place_id: str | None = None,
        name: str | None = None,
    ) -> int | None:
        """수동 DB에서 인당 가격 조회."""
        prices = self._load_json(self._prices_path)
        for key in (naver_place_id, place_id, _normalize_key(name or "")):
            if key and key in prices:
                return prices[key].get("price_per_person_krw")
        return None

    def get_opening_date(
        self,
        *,
        place_id: str | None = None,
        naver_place_id: str | None = None,
        name: str | None = None,
    ) -> date | None:
        """수동 DB에서 개업일 조회."""
        openings = self._load_json(self._openings_path)
        for key in (naver_place_id, place_id, _normalize_key(name or "")):
            if key and key in openings:
                raw = openings[key].get("opened_at")
                if raw:
                    return date.fromisoformat(raw)
        return None

    def upsert_price(
        self,
        key: str,
        price_per_person_krw: int,
        notes: str = "",
    ) -> None:
        """가격 수동 등록/갱신."""
        prices = self._load_json(self._prices_path)
        prices[key] = {
            "price_per_person_krw": price_per_person_krw,
            "notes": notes,
            "updated_at": datetime.now().isoformat(),
        }
        self._save_json(self._prices_path, prices)
        logger.info("수동 가격 저장: %s = %d원", key, price_per_person_krw)

    def upsert_opening(self, key: str, opened_at: date, name: str = "") -> None:
        """개업일 수동 등록/갱신."""
        openings = self._load_json(self._openings_path)
        openings[key] = {
            "opened_at": opened_at.isoformat(),
            "name": name,
            "updated_at": datetime.now().isoformat(),
        }
        self._save_json(self._openings_path, openings)
        logger.info("수동 개업일 저장: %s = %s", key, opened_at)

    # --- 크롤링 캐시 (TTL) ---

    def get_cached_detail(self, naver_place_id: str, ttl_hours: int = 24) -> dict[str, Any] | None:
        cache = self._load_json(self._cache_path)
        entry = cache.get(naver_place_id)
        if not entry:
            return None
        fetched = datetime.fromisoformat(entry.get("fetched_at", "2000-01-01"))
        if datetime.now() - fetched > timedelta(hours=ttl_hours):
            return None
        return entry.get("data")

    def set_cached_detail(self, naver_place_id: str, data: dict[str, Any]) -> None:
        try:
            cache = self._load_json(self._cache_path)
            cache[naver_place_id] = {
                "fetched_at": datetime.now().isoformat(),
                "data": data,
            }
            self._save_json(self._cache_path, cache)
        except OSError as exc:
            logger.warning("캐시 저장 실패 (id=%s): %s", naver_place_id, exc)
