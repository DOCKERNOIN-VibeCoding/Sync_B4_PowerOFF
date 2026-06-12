"""콘솔 상태 표시와 Tkinter 카운트다운 다이얼로그."""

from __future__ import annotations

from monitor import MonitorStatus


def format_rate(bytes_per_sec: float) -> str:
    """byte/sec 값을 사람이 읽기 쉬운 문자열로."""
    if bytes_per_sec < 0:
        return "측정중..."
    units = ["B/s", "KB/s", "MB/s", "GB/s"]
    value = float(bytes_per_sec)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:6.1f} {unit}"
        value /= 1024
    return f"{value:6.1f} {units[-1]}"


def render_status(status: MonitorStatus) -> None:
    """현재 모니터 상태를 콘솔에 출력한다."""
    print("-" * 56)
    for svc in status.services:
        if not svc.running:
            state = "미실행(동기화 없음)"
        elif svc.idle:
            state = "대기중(idle)"
        else:
            state = "동기화중..."
        print(f"  {svc.name:<14} {format_rate(svc.rate):>12}  {state}")
    print(f"  {'시스템 업로드':<14} {format_rate(status.net_rate):>12}")

    if status.downloads_count > 0:
        dl_state = "진행중..." if status.downloads_active else "정체/대기"
        print(f"  {'브라우저 다운로드':<14} {status.downloads_count}개          {dl_state}")

    if status.overall_idle:
        remain = max(0.0, status.stabilize_target - status.idle_seconds)
        print(
            f"  >> 안정화 진행: {status.idle_seconds:5.0f}s / "
            f"{status.stabilize_target:.0f}s (완료까지 약 {remain:.0f}s)"
        )
    else:
        print("  >> 동기화 활동 감지됨 - 안정화 타이머 리셋")
    print(f"  (총 가동 {status.runtime_seconds:.0f}s)")


def countdown_dialog(seconds: int) -> str:
    """종료 직전 카운트다운 창을 띄운다.

    Returns:
        "shutdown" — 카운트다운 만료 또는 '지금 종료' 클릭
        "cancel"   — '취소' 클릭 또는 창 닫음
    """
    import tkinter as tk

    result = {"value": "cancel"}
    root = tk.Tk()
    root.title("Sync_B4_PowerOFF")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    remaining = {"n": seconds}

    msg = tk.Label(
        root,
        text="모든 동기화가 완료되었습니다.",
        font=("Segoe UI", 11, "bold"),
        padx=24,
        pady=(0),
    )
    msg.pack(padx=24, pady=(20, 4))

    countdown_label = tk.Label(root, text="", font=("Segoe UI", 10))
    countdown_label.pack(padx=24, pady=(0, 12))

    def finish(value: str) -> None:
        result["value"] = value
        try:
            root.destroy()
        except tk.TclError:
            pass

    def tick() -> None:
        n = remaining["n"]
        countdown_label.config(text=f"{n}초 후 PC를 종료합니다.")
        if n <= 0:
            finish("shutdown")
            return
        remaining["n"] = n - 1
        root.after(1000, tick)

    btn_frame = tk.Frame(root)
    btn_frame.pack(padx=24, pady=(0, 18))

    tk.Button(
        btn_frame, text="취소", width=12, command=lambda: finish("cancel")
    ).pack(side="left", padx=6)
    tk.Button(
        btn_frame, text="지금 종료", width=12, command=lambda: finish("shutdown")
    ).pack(side="left", padx=6)

    root.protocol("WM_DELETE_WINDOW", lambda: finish("cancel"))

    # 화면 중앙 배치
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"+{x}+{y}")

    tick()
    root.mainloop()
    return result["value"]
