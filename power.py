"""Windows 전원 종료 래퍼."""

from __future__ import annotations

import subprocess


def shutdown(delay_seconds: int = 5, comment: str = "Sync_B4_PowerOFF: 동기화 완료 후 자동 종료") -> None:
    """PC를 종료한다. delay_seconds 동안은 `shutdown /a`로 취소 가능."""
    subprocess.run(
        ["shutdown", "/s", "/t", str(delay_seconds), "/c", comment],
        check=True,
    )


def abort() -> None:
    """예약된 종료를 취소한다(이미 예약이 없으면 조용히 무시)."""
    subprocess.run(["shutdown", "/a"], check=False)
