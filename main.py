"""Sync_B4_PowerOFF — 동기화 완료 후 자동 종료.

퇴근할 때 실행하면 OneDrive / Google Drive 등의 동기화가 모두 끝날 때까지
기다렸다가, 완료되면 카운트다운 후 PC를 자동으로 종료한다.

사용법:
    python main.py            # 일반 실행 (완료 시 실제 종료)
    python main.py --dry-run  # 종료는 하지 않고 동작만 확인(테스트용)
    python main.py --countdown 30
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

import config
import power
import ui
from detectors import discover_services
from monitor import SyncMonitor


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("sync_b4_poweroff")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S")

    fh = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


def main() -> int:
    parser = argparse.ArgumentParser(description="동기화 완료 후 자동 종료")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제로 종료하지 않고 동작만 확인",
    )
    parser.add_argument(
        "--countdown",
        type=int,
        default=config.COUNTDOWN_SECONDS,
        help="종료 직전 카운트다운(초)",
    )
    args = parser.parse_args()

    # 일부 콘솔(cp949 등)에서 인코딩 불가 문자로 죽지 않도록 방어
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

    log = setup_logging()

    print("=" * 56)
    print("  Sync_B4_PowerOFF — 동기화 완료 후 자동 종료")
    if args.dry_run:
        print("  [DRY-RUN] 실제 종료는 하지 않습니다.")
    print("=" * 56)
    log.info("시작 (dry_run=%s)", args.dry_run)

    # 시작 시점 서비스 상태 안내
    services = discover_services(config.WATCHED_SERVICES)
    for name, svc in services.items():
        state = f"실행중 (PID {len(svc.procs)}개)" if svc.running else "미실행"
        print(f"  - {name}: {state}")
    if not any(s.running for s in services.values()):
        print("  ! 감시 대상이 하나도 실행 중이 아닙니다. 안정화 후 그대로 종료합니다.")
    print(f"\n  {config.SAMPLE_INTERVAL:.0f}초 간격으로 감시합니다. (Ctrl+C 로 중단)\n")

    monitor = SyncMonitor()

    try:
        while True:
            status = monitor.tick()
            ui.render_status(status)
            log.info(
                "idle=%.0fs net=%.0fB/s overall_idle=%s",
                status.idle_seconds,
                status.net_rate,
                status.overall_idle,
            )
            if status.synced:
                print("\n  [완료] 모든 동기화가 완료되었습니다.\n")
                log.info("동기화 완료 판정")
                break
            time.sleep(config.SAMPLE_INTERVAL)
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
        log.info("사용자 중단(KeyboardInterrupt)")
        return 0

    # 카운트다운 다이얼로그
    choice = ui.countdown_dialog(args.countdown)
    if choice == "cancel":
        print("종료가 취소되었습니다. 프로그램을 종료합니다.")
        log.info("사용자가 종료 취소")
        return 0

    log.info("종료 실행 (choice=%s)", choice)
    if args.dry_run:
        print("[DRY-RUN] 실제로는 여기서 PC가 종료됩니다.")
        return 0

    print("PC를 종료합니다...")
    power.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
