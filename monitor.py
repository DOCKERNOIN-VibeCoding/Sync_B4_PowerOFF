"""SyncMonitor: 감시 대상 프로세스의 I/O를 샘플링해 동기화 완료를 판정한다.

판정 원리
---------
- 각 서비스(OneDrive, Google Drive 등)에 속한 프로세스들의 누적 I/O(read+write+other)를
  주기적으로 읽어 직전 샘플과의 차이로 byte/sec 속도를 구한다.
- 모든 서비스의 속도가 임계값 미만이고, 시스템 업로드도 잠잠하면 그 순간을 'idle'로 본다.
- idle 상태가 STABILIZE_SECONDS 동안 '연속'으로 유지되면 동기화 완료로 판정한다.
- 프로세스가 재시작되면(PID 집합 변화) 해당 tick은 '활동 중'으로 보고 기준선을 다시 잡는다.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import psutil

import config
from detectors import discover_services, find_partial_downloads


@dataclass
class ServiceStatus:
    name: str
    running: bool
    rate: float  # bytes/sec (직전 tick 대비). 측정 불가/첫 tick이면 -1
    idle: bool


@dataclass
class MonitorStatus:
    services: list[ServiceStatus] = field(default_factory=list)
    net_rate: float = 0.0          # 시스템 업로드 bytes/sec
    overall_idle: bool = False
    idle_seconds: float = 0.0      # 현재까지 연속 idle 유지 시간
    runtime_seconds: float = 0.0   # 모니터 시작 후 경과 시간
    stabilize_target: float = config.STABILIZE_SECONDS
    synced: bool = False
    any_running: bool = False
    downloads_count: int = 0       # 현재 진행 중(임시 파일) 다운로드 개수
    downloads_active: bool = False  # 이번 tick에 다운로드가 자라고 있었는가


def _service_total_io(procs: list[psutil.Process]) -> tuple[int, frozenset[int]]:
    """프로세스 묶음의 누적 I/O 합계와 현재 PID 집합을 반환."""
    total = 0
    pids: set[int] = set()
    for proc in procs:
        try:
            io = proc.io_counters()
            total += io.read_bytes + io.write_bytes + getattr(io, "other_bytes", 0)
            pids.add(proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return total, frozenset(pids)


class SyncMonitor:
    def __init__(self) -> None:
        self._start = time.monotonic()
        self._last_time: float | None = None
        # 서비스별 직전 (누적 I/O, PID 집합)
        self._prev_io: dict[str, tuple[int, frozenset[int]]] = {}
        self._prev_net: int | None = None
        # 직전 tick의 진행 중 다운로드 (경로 -> 크기)
        self._prev_downloads: dict[str, int] = {}
        self._idle_seconds = 0.0

    def tick(self) -> MonitorStatus:
        """한 번 샘플링하고 갱신된 상태를 반환한다."""
        now = time.monotonic()
        elapsed = (now - self._last_time) if self._last_time is not None else 0.0
        first_tick = self._last_time is None

        services_now = discover_services(config.WATCHED_SERVICES)
        statuses: list[ServiceStatus] = []
        any_running = False
        all_idle = True

        for name, svc in services_now.items():
            running = svc.running
            any_running = any_running or running
            total, pids = _service_total_io(svc.procs)
            prev = self._prev_io.get(name)
            rate = -1.0
            idle = True

            if not running:
                # 실행 중이 아니면 동기화할 것이 없으므로 idle 취급
                idle = True
            elif first_tick or prev is None:
                # 첫 샘플은 기준선만 잡고 활동 중으로 본다
                idle = False
            elif pids != prev[1]:
                # 프로세스 재시작 등 PID 변화 → 이번 tick은 활동 중으로 간주
                idle = False
            elif elapsed > 0:
                delta = max(0, total - prev[0])
                rate = delta / elapsed
                idle = rate < config.IDLE_BYTES_PER_SEC

            self._prev_io[name] = (total, pids)
            all_idle = all_idle and idle
            statuses.append(ServiceStatus(name=name, running=running, rate=rate, idle=idle))

        # 시스템 업로드 속도
        net_now = psutil.net_io_counters().bytes_sent
        net_rate = 0.0
        net_idle = True
        if self._prev_net is not None and elapsed > 0:
            net_rate = max(0, net_now - self._prev_net) / elapsed
            net_idle = net_rate < config.NET_IDLE_BYTES_PER_SEC
        elif first_tick:
            net_idle = False  # 첫 tick은 보수적으로 활동 중
        self._prev_net = net_now

        # 브라우저 다운로드 진행 감지 (확장자 기반, 브라우저 종류 무관)
        downloads = find_partial_downloads(
            config.DOWNLOAD_DIRS, config.PARTIAL_DOWNLOAD_EXTENSIONS
        )
        downloads_active = False
        for path, size in downloads.items():
            prev_size = self._prev_downloads.get(path)
            # 새로 나타났거나 크기가 커졌으면 다운로드가 진행 중
            if prev_size is None or size > prev_size:
                downloads_active = True
        self._prev_downloads = downloads

        overall_idle = (not first_tick) and all_idle and net_idle and not downloads_active

        # 연속 idle 누적 시간 갱신
        if overall_idle and not first_tick:
            self._idle_seconds += elapsed
        else:
            self._idle_seconds = 0.0

        runtime = now - self._start
        synced = (
            overall_idle
            and runtime >= config.MIN_RUNTIME_SECONDS
            and self._idle_seconds >= config.STABILIZE_SECONDS
        )

        self._last_time = now

        return MonitorStatus(
            services=statuses,
            net_rate=net_rate,
            overall_idle=overall_idle,
            idle_seconds=self._idle_seconds,
            runtime_seconds=runtime,
            synced=synced,
            any_running=any_running,
            downloads_count=len(downloads),
            downloads_active=downloads_active,
        )
