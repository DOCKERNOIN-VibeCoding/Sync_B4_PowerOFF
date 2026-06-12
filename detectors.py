"""감시 대상 동기화 프로세스를 찾아내는 모듈."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import psutil


@dataclass
class ServiceProcesses:
    """한 서비스(예: OneDrive)에 속한 실행 중 프로세스 묶음."""

    name: str
    exe_names: list[str]
    procs: list[psutil.Process] = field(default_factory=list)

    @property
    def running(self) -> bool:
        return len(self.procs) > 0


def find_service_processes(name: str, exe_names: list[str]) -> ServiceProcesses:
    """주어진 실행 파일 이름 목록에 해당하는 모든 프로세스를 수집한다.

    GoogleDriveFS 처럼 여러 PID로 동작하는 경우 모두 모은다.
    """
    targets = {e.lower() for e in exe_names}
    procs: list[psutil.Process] = []
    for proc in psutil.process_iter(["name"]):
        try:
            pname = (proc.info.get("name") or "").lower()
            if pname in targets:
                procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return ServiceProcesses(name=name, exe_names=exe_names, procs=procs)


def discover_services(watched: dict[str, list[str]]) -> dict[str, ServiceProcesses]:
    """설정의 모든 서비스를 탐지해 이름->ServiceProcesses 매핑으로 반환."""
    return {
        name: find_service_processes(name, exe_names)
        for name, exe_names in watched.items()
    }


def find_partial_downloads(
    dirs: list[str], exts: list[str]
) -> dict[str, int]:
    """다운로드 폴더에서 진행 중(임시 확장자) 파일을 찾아 경로->크기 매핑으로 반환.

    브라우저 종류와 무관하게 확장자(.crdownload/.part 등)로 판단한다.
    """
    result: dict[str, int] = {}
    suffixes = {e.lower() for e in exts}
    for d in dirs:
        base = Path(d)
        if not base.is_dir():
            continue
        try:
            for entry in base.iterdir():
                if entry.suffix.lower() in suffixes:
                    try:
                        result[str(entry)] = entry.stat().st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return result
