"""
로깅 설정.

모듈별 logger를 일관된 포맷으로 사용할 수 있게 합니다.
"""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """루트 로거에 콘솔 핸들러와 포맷을 설정합니다."""
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # 중복 핸들러 방지
    if not root.handlers:
        root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """모듈 이름 기반 logger를 반환합니다."""
    return logging.getLogger(name)
