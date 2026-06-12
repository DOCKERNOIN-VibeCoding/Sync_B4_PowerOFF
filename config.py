"""Sync_B4_PowerOFF 설정값.

여기 값만 바꾸면 감지 민감도와 동작을 조정할 수 있습니다.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# 감시 대상 동기화 프로세스
# ---------------------------------------------------------------------------
# key: 화면에 표시할 이름, value: 매칭할 실행 파일 이름 목록(소문자 비교)
WATCHED_SERVICES: dict[str, list[str]] = {
    "OneDrive": ["onedrive.exe"],
    "Google Drive": ["googledrivefs.exe"],
}

# ---------------------------------------------------------------------------
# 브라우저 다운로드 진행 감지
# ---------------------------------------------------------------------------
# 크롬/웨일/엣지(.crdownload), Firefox(.part), Opera(.opdownload), Safari(.download)
# 등은 받는 중인 파일을 아래 확장자로 만든다. 다운로드 폴더에서 이 임시 파일이
# '자라고 있는지'를 보면 브라우저 종류와 무관하게 다운로드 진행을 감지할 수 있다.
DOWNLOAD_DIRS: list[str] = [
    str(Path.home() / "Downloads"),
]

PARTIAL_DOWNLOAD_EXTENSIONS: list[str] = [
    ".crdownload",   # Chrome / Whale / Edge 등 Chromium 계열
    ".part",         # Firefox
    ".opdownload",   # Opera
    ".download",     # Safari
]

# ---------------------------------------------------------------------------
# 감지 파라미터 (튜닝 지점)
# ---------------------------------------------------------------------------
# I/O 샘플링 간격(초)
SAMPLE_INTERVAL: float = 5.0

# 이 속도(byte/sec) 미만이면 해당 프로세스를 'idle'로 간주
IDLE_BYTES_PER_SEC: float = 50 * 1024  # 50 KB/s

# 시스템 전체 업로드가 이 속도 미만이어야 idle 보조 조건 충족
NET_IDLE_BYTES_PER_SEC: float = 100 * 1024  # 100 KB/s

# 모든 대상이 연속으로 이 시간(초)만큼 idle을 유지해야 '동기화 완료'로 판정
STABILIZE_SECONDS: float = 90.0

# 프로그램 시작 후 최소 이 시간(초)이 지나야 완료 판정을 허용
# (실행 직후 잠깐 idle처럼 보이는 구간 방지)
MIN_RUNTIME_SECONDS: float = 30.0

# 종료 직전 카운트다운(초)
COUNTDOWN_SECONDS: int = 60

# ---------------------------------------------------------------------------
# 로깅
# ---------------------------------------------------------------------------
LOG_FILE: str = "sync_b4_poweroff.log"
