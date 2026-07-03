"""
Windows 콘솔 UTF-8 설정.

한글 출력 깨짐(cp949) 방지를 위해 stdout/stderr 인코딩을 UTF-8로 맞춥니다.
"""

import os
import sys


def configure_utf8_console() -> None:
    """
    Windows에서 UTF-8 콘솔 출력을 활성화합니다.

    1. PYTHONUTF8 환경 변수 설정
    2. stdout/stderr reconfigure (Python 3.7+)
    3. chcp 65001 실행 (cmd/PowerShell 코드 페이지)
  """
    os.environ.setdefault("PYTHONUTF8", "1")

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass

    if sys.platform == "win32":
        try:
            os.system("chcp 65001 >nul 2>&1")
        except OSError:
            pass
