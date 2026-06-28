"""GUI: 감시 진행과 종료 카운트다운을 보여주는 작은 팝업 창.

콘솔 없이 동작하도록, 모니터 샘플링도 이 창의 이벤트 루프에서 직접 구동한다.

- 감시 단계: 안정화까지 남은 시간을 큰 시계로, 터미널 한 줄 요약을 그 아래 작게 표시.
- 종료 단계: 동기화 완료 안내 후 카운트다운, '취소' / '지금 종료' 버튼 제공.
"""

from __future__ import annotations

import logging
import os
import sys
import time

import config
from monitor import MonitorStatus, SyncMonitor


def _resource_path(name: str) -> str:
    """개발 실행과 PyInstaller 번들 모두에서 리소스 절대경로를 돌려준다."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)

# 팝업 색상 팔레트 (다크 카드)
_BG = "#1e1e2e"
_FG = "#e6e6f0"
_SUB = "#9aa0b5"
_ACCENT = "#89b4fa"
_WARN = "#f9e2af"

# 폰트: 제목이 가장 크고, 모니터링 표시는 카운트다운 숫자의 절반 정도.
_FONT_TITLE = ("Segoe UI", 18, "bold")
_FONT_DESC = ("Segoe UI", 11)
_FONT_CLOCK = ("Segoe UI", 34, "bold")   # 카운트다운 숫자
_FONT_STATE = ("Segoe UI", 17, "bold")   # "모니터링 중" 등 단어 표시
_FONT_SMALL = ("Segoe UI", 9)


def format_rate(bytes_per_sec: float) -> str:
    """byte/sec 값을 사람이 읽기 쉬운 문자열로."""
    if bytes_per_sec < 0:
        return "측정중..."
    units = ["B/s", "KB/s", "MB/s", "GB/s"]
    value = float(bytes_per_sec)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} {units[-1]}"


def format_clock(seconds: float) -> str:
    """초를 M:SS 시계 문자열로."""
    s = max(0, int(round(seconds)))
    return f"{s // 60}:{s % 60:02d}"


def status_summary(status: MonitorStatus) -> str:
    """모니터 상태를 한 줄로 요약한다(터미널 내용 대체)."""
    if status.downloads_active:
        return f"브라우저 다운로드 {status.downloads_count}개 진행 중"

    active = [s for s in status.services if s.running and not s.idle]
    if active:
        parts = [f"{s.name} {format_rate(s.rate)}" for s in active]
        return "동기화 중 · " + ", ".join(parts)

    if status.net_rate >= config.NET_IDLE_BYTES_PER_SEC:
        return f"업로드 중 · {format_rate(status.net_rate)}"

    running = [s for s in status.services if s.running]
    if not running:
        return "감시 대상 미실행 — 안정화 측정 중"
    return "대기(idle) — 안정화 측정 중"


class CountdownApp:
    """감시 → 종료 카운트다운을 하나의 작은 창에서 처리한다.

    run()의 반환값:
        "shutdown" — 카운트다운 만료 또는 '지금 종료' 클릭
        "cancel"   — '중단'/'취소' 클릭 또는 창 닫음
    """

    def __init__(
        self,
        monitor: SyncMonitor,
        countdown_seconds: int,
        dry_run: bool,
        log: logging.Logger,
    ) -> None:
        self._monitor = monitor
        self._countdown_seconds = countdown_seconds
        self._dry_run = dry_run
        self._log = log

        self._result = "cancel"
        self._phase = "watch"  # "watch" | "countdown"
        self._status: MonitorStatus | None = None
        self._last_sample: float | None = None
        self._shutdown_deadline: float | None = None

    # -- 외부 진입점 ---------------------------------------------------------
    def run(self) -> str:
        import tkinter as tk

        self._tk = tk
        root = tk.Tk()
        self._root = root
        root.title("Sync_B4_PowerOFF")
        try:
            root.iconbitmap(_resource_path("icon.ico"))
        except tk.TclError:
            pass
        root.configure(bg=_BG)
        root.resizable(False, False)
        root.attributes("-topmost", True)
        root.protocol("WM_DELETE_WINDOW", lambda: self._finish("cancel"))

        pad = {"bg": _BG}
        # 창의 정체를 알려주는 고정 머리말(단계와 무관하게 항상 표시).
        self._app_title = tk.Label(
            root,
            text="자동 종료 프로세스 실행 중",
            font=_FONT_TITLE,
            fg=_FG,
            **pad,
        )
        self._app_title.pack(padx=28, pady=(18, 0))

        self._app_desc = tk.Label(
            root,
            text="모든 동기화 프로세스를 마무리한 후 자동 종료합니다.",
            font=_FONT_DESC,
            fg=_SUB,
            **pad,
        )
        self._app_desc.pack(padx=28, pady=(1, 8))

        self._clock = tk.Label(
            root,
            text="--:--",
            font=_FONT_CLOCK,
            fg=_ACCENT,
            **pad,
        )
        self._clock.pack(padx=28, pady=(0, 0))

        self._caption = tk.Label(
            root, text="", font=_FONT_SMALL, fg=_SUB, **pad
        )
        self._caption.pack(padx=28, pady=(0, 2))

        self._summary = tk.Label(
            root,
            text="시작하는 중...",
            font=_FONT_SMALL,
            fg=_SUB,
            wraplength=320,
            **pad,
        )
        self._summary.pack(padx=28, pady=(0, 10))

        self._btns = tk.Frame(root, bg=_BG)
        self._btns.pack(padx=28, pady=(0, 16))
        self._build_watch_buttons()

        self._center(root)
        root.after(300, self._ui_tick)
        root.mainloop()
        return self._result

    # -- 버튼 구성 ----------------------------------------------------------
    def _button(self, parent, text, command, accent=False):
        return self._tk.Button(
            parent,
            text=text,
            width=12,
            command=command,
            relief="flat",
            bd=0,
            cursor="hand2",
            fg=_BG if accent else _FG,
            bg=_ACCENT if accent else "#313244",
            activebackground=_ACCENT if accent else "#45475a",
            activeforeground=_BG if accent else _FG,
            font=("Segoe UI", 9, "bold"),
        )

    def _clear_buttons(self) -> None:
        for child in self._btns.winfo_children():
            child.destroy()

    def _build_watch_buttons(self) -> None:
        self._clear_buttons()
        self._button(
            self._btns, "중단", lambda: self._finish("cancel")
        ).pack(side="left", padx=6)

    def _build_countdown_buttons(self) -> None:
        self._clear_buttons()
        self._button(
            self._btns, "취소", lambda: self._finish("cancel")
        ).pack(side="left", padx=6)
        self._button(
            self._btns, "지금 종료", lambda: self._finish("shutdown"), accent=True
        ).pack(side="left", padx=6)

    # -- 메인 루프 (1초 주기) ------------------------------------------------
    def _ui_tick(self) -> None:
        now = time.monotonic()

        if self._phase == "watch":
            need_sample = (
                self._last_sample is None
                or now - self._last_sample >= config.SAMPLE_INTERVAL
            )
            if need_sample:
                self._status = self._monitor.tick()
                self._last_sample = now
                self._log_status(self._status)
                if self._status.synced:
                    self._enter_countdown(now)
                    self._root.after(1000, self._ui_tick)
                    return
            self._render_watch(now)
        else:
            self._render_countdown(now)

        self._root.after(1000, self._ui_tick)

    # -- 렌더링 -------------------------------------------------------------
    def _render_watch(self, now: float) -> None:
        status = self._status
        if status is None:
            return
        since = now - self._last_sample if self._last_sample else 0.0

        if status.overall_idle:
            idle = status.idle_seconds + since
            remain = max(0.0, status.stabilize_target - idle)
            self._clock.config(text=format_clock(remain), font=_FONT_CLOCK, fg=_ACCENT)
            self._caption.config(text="안정화 완료까지 (활동 감지 시 리셋)")
        else:
            self._clock.config(text="모니터링 중", font=_FONT_STATE, fg=_WARN)
            self._caption.config(text="동기화 활동 감지됨 — 안정화 타이머 리셋")

        self._summary.config(text=status_summary(status))

    def _enter_countdown(self, now: float) -> None:
        self._phase = "countdown"
        self._shutdown_deadline = now + self._countdown_seconds
        self._build_countdown_buttons()
        self._render_countdown(now)

    def _render_countdown(self, now: float) -> None:
        remain = max(0.0, (self._shutdown_deadline or now) - now)
        self._clock.config(text=format_clock(remain), font=_FONT_CLOCK, fg=_WARN)
        tail = " (DRY-RUN: 실제 종료 안 함)" if self._dry_run else ""
        self._caption.config(text=f"동기화 완료 — 잠시 후 PC를 종료합니다.{tail}")
        self._summary.config(text="'취소'를 누르면 종료하지 않습니다.")
        if remain <= 0:
            self._finish("shutdown")

    # -- 보조 ---------------------------------------------------------------
    def _log_status(self, status: MonitorStatus) -> None:
        self._log.info(
            "idle=%.0fs net=%.0fB/s overall_idle=%s | %s",
            status.idle_seconds,
            status.net_rate,
            status.overall_idle,
            status_summary(status),
        )

    def _finish(self, value: str) -> None:
        self._result = value
        try:
            self._root.destroy()
        except self._tk.TclError:
            pass

    @staticmethod
    def _center(root) -> None:
        root.update_idletasks()
        w, h = root.winfo_width(), root.winfo_height()
        x = (root.winfo_screenwidth() - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f"+{x}+{y}")
