# Sync_B4_PowerOFF

**동기화가 끝난 뒤에 PC를 자동으로 꺼주는 프로그램입니다.**

파일을 수정한 직후 PC를 끄면 OneDrive·Google Drive 동기화가 끝나기 전에 전원이 차단되어,
다른 기기에서 최신 내용이 보이지 않는 문제가 생깁니다.
이 프로그램은 **퇴근할 때 실행**해 두면, 모든 동기화가 끝날 때까지 기다렸다가
완료되면 **카운트다운 후 자동으로 PC를 종료**합니다.

---

## 동작 방식

다음 세 가지를 함께 감시하여, **모두 잠잠해진 뒤에만** 종료합니다.

1. **클라우드 동기화** — OneDrive(`OneDrive.exe`), Google Drive(`GoogleDriveFS.exe`) 프로세스의
   **디스크/네트워크 I/O**를 주기적으로 측정합니다.
2. **브라우저 다운로드** — 크롬·네이버 웨일·엣지(`.crdownload`), Firefox(`.part`), Opera(`.opdownload`),
   Safari(`.download`) 등은 받는 중인 파일을 임시 확장자로 만듭니다.
   **다운로드 폴더에서 이 임시 파일이 자라고 있는지**를 보고 다운로드 진행을 감지합니다.
   브라우저 종류와 상관없이 동작합니다.
3. **업로드(웹 업로드 포함)** — **시스템 전체 업로드 속도**를 함께 봅니다.
   브라우저든 다른 앱이든 무언가 활발히 업로드 중이면 종료를 보류합니다.

위 세 신호가 일정 시간(기본 90초) 동안 **연속으로 잠잠하면** 모든 작업이 끝난 것으로 판단하고,
**카운트다운 창**(기본 60초)을 띄운 뒤 PC를 종료합니다. 창에서 **[취소]**를 누르면 중단됩니다.

> 참고: Google Drive·브라우저 업로드는 공개된 "완료" API가 없어 활동량으로 간접 판단합니다.
> 100% 정확하지는 않으므로, 안전을 위해 안정화 시간을 넉넉하게 잡아 두었습니다.
>
> 브라우저 프로세스 자체(chrome.exe 등)는 가만히 있어도 백그라운드 통신이 많아
> 감시 목록에 넣지 않았습니다. 대신 위의 다운로드 파일 감지 + 시스템 업로드 감지가 더 정확합니다.

---

## 설치

1. [Python](https://www.python.org/) 3.10 이상 설치 (설치 시 *Add Python to PATH* 체크)
2. 의존성 설치:

   ```bash
   pip install -r requirements.txt
   ```

   > `tkinter`(카운트다운 창)는 Python에 기본 포함되어 별도 설치가 필요 없습니다.

---

## 사용법

### 일반 실행 (퇴근할 때)

```bash
python main.py
```

또는 `run.bat`을 더블클릭하세요. 동기화가 모두 끝나면 카운트다운 후 PC가 꺼집니다.

### 테스트 (실제로 끄지 않음)

```bash
python main.py --dry-run
```

동작만 확인하고 실제 종료는 하지 않습니다. **처음 사용 전 반드시 이 모드로 한 번 확인하세요.**

### 카운트다운 시간 변경

```bash
python main.py --countdown 30
```

실행 중 **Ctrl+C**로 언제든 중단할 수 있습니다.

---

## 설정 변경

[config.py](config.py)에서 감지 민감도를 조정할 수 있습니다.

| 항목 | 기본값 | 설명 |
|------|--------|------|
| `WATCHED_SERVICES` | OneDrive, Google Drive | 감시할 프로그램(실행 파일 이름) |
| `DOWNLOAD_DIRS` | 사용자 Downloads 폴더 | 브라우저 다운로드를 감시할 폴더 |
| `PARTIAL_DOWNLOAD_EXTENSIONS` | .crdownload/.part 등 | 진행 중 다운로드로 볼 임시 확장자 |
| `SAMPLE_INTERVAL` | 5초 | I/O 측정 간격 |
| `IDLE_BYTES_PER_SEC` | 50 KB/s | 이 속도 미만이면 '대기 중'으로 판단 |
| `STABILIZE_SECONDS` | 90초 | 이 시간 동안 연속 대기해야 '완료'로 판정 |
| `MIN_RUNTIME_SECONDS` | 30초 | 시작 후 최소 이 시간은 종료 판정 보류 |
| `COUNTDOWN_SECONDS` | 60초 | 종료 직전 카운트다운 |

다른 동기화 프로그램(예: Dropbox)을 추가하려면 `WATCHED_SERVICES`에 항목을 더하면 됩니다.

```python
WATCHED_SERVICES = {
    "OneDrive": ["onedrive.exe"],
    "Google Drive": ["googledrivefs.exe"],
    "Dropbox": ["dropbox.exe"],   # 예시
}
```

---

## 파일 구성

| 파일 | 역할 |
|------|------|
| `main.py` | 진입점 · 전체 흐름 제어 |
| `monitor.py` | I/O 샘플링 및 동기화 완료 판정 |
| `detectors.py` | 감시 대상 프로세스 탐지 |
| `ui.py` | 콘솔 상태 표시 · 카운트다운 창 |
| `power.py` | PC 종료/취소 명령 |
| `config.py` | 설정값 |

---

## 주의

- **Windows 전용**입니다.
- I/O 기반 추정이므로 매우 느린 회선 등에서는 오판 가능성이 있습니다.
  중요한 작업 직후에는 `--dry-run`으로 동작을 먼저 확인하길 권장합니다.
- 종료가 시작되어도 카운트다운 창의 **[취소]** 또는 명령창의 `shutdown /a`로 중단할 수 있습니다.
