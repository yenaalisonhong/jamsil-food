"""
Monthly Wrapped 출력 렌더러.

MVP: 콘솔/터미널 텍스트+이모지 (옵션 B)
확장: HtmlWrappedRenderer → PNG export (옵션 A)
"""

from abc import ABC, abstractmethod

from models.wrapped import WrappedReport


class WrappedRenderer(ABC):
    """Wrapped 리포트 출력 추상 인터페이스."""

    @abstractmethod
    def render(self, report: WrappedReport) -> str:
        """리포트를 문자열로 렌더링합니다."""


class ConsoleWrappedRenderer(WrappedRenderer):
    """터미널 슬라이드형 출력 (스포티파이 Wrapped 톤)."""

    def render(self, report: WrappedReport) -> str:
        lines: list[str] = []
        divider = "═" * 40

        lines.append("")
        lines.append(divider)
        lines.append(f"  🍽️  {report.month_label} 맛집 Wrapped")
        lines.append(divider)

        for i, card in enumerate(report.cards, start=1):
            lines.append("")
            lines.append(f"  [{i}/{len(report.cards)}] {card.emoji}  {card.title}")
            lines.append(f"       {card.subtitle}")
            if card.stat_label:
                lines.append(f"       ▶ {card.stat_label}: {card.stat_value}")

        lines.append("")
        lines.append(divider)
        lines.append("  공유하고 싶다면 스크린샷을 찍어보세요 📸")
        lines.append(divider)
        lines.append("")

        return "\n".join(lines)

    def print(self, report: WrappedReport) -> None:
        """stdout에 바로 출력합니다."""
        print(self.render(report))
