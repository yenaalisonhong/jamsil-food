"""
식사 기록 데이터 어댑터.

브라우저 localStorage export JSON 등 다양한 소스에서
DiaryStore를 읽어옵니다.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from models.diary import DiaryStore
from utils.logger import get_logger

logger = get_logger(__name__)


class DiaryAdapter(ABC):
    """식사 기록 로드 추상 인터페이스."""

    @abstractmethod
    def load(self) -> DiaryStore:
        """전체 식사 기록을 반환합니다."""


class FileDiaryAdapter(DiaryAdapter):
    """JSON 파일에서 식사 기록을 읽습니다."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def load(self) -> DiaryStore:
        if not self._path.exists():
            logger.warning("다이어리 파일 없음: %s — 빈 저장소 반환", self._path)
            return DiaryStore()

        try:
            raw: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("다이어리 파일 읽기 실패: %s (%s)", self._path, exc)
            return DiaryStore()

        return DiaryStore.from_raw(raw)
