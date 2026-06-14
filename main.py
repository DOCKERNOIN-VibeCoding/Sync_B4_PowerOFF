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

import config
import power
import ui
from detectors import discover_services
from monitor import SyncMonitor


def setup_logging() -> logging.Logger:
    # 로그 파일을 남기지 않는다. 진행 상황은 팝업 UI로만 보여준다.
    # (log.info 호출은 그대로 두되, 출력 핸들러는 NullHandler로 흘려보낸다.)
    logger = logging.getLogger("sync_b4_poweroff")
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.NullHandler())
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

    log = setup_logging()
    log.info("시작 (dry_run=%s)", args.dry_run)

    # 시작 시점 서비스 상태 기록(핸들러가 없으므로 실제 출력은 없음).
    services = discover_services(config.WATCHED_SERVICES)
    for name, svc in services.items():
        state = f"실행중 (PID {len(svc.procs)}개)" if svc.running else "미실행"
        log.info("  - %s: %s", name, state)
    if not any(s.running for s in services.values()):
        log.info("  ! 감시 대상이 하나도 실행 중이 아닙니다. 안정화 후 그대로 종료합니다.")

    # 감시와 종료 카운트다운을 작은 팝업 창에서 모두 처리한다.
    monitor = SyncMonitor()
    app = ui.CountdownApp(monitor, args.countdown, args.dry_run, log)
    choice = app.run()

    if choice == "cancel":
        log.info("사용자가 종료를 취소/중단")
        return 0

    log.info("동기화 완료 판정 — 종료 실행 (choice=%s)", choice)
    if args.dry_run:
        log.info("[DRY-RUN] 실제로는 여기서 PC가 종료됩니다.")
        return 0

    power.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
