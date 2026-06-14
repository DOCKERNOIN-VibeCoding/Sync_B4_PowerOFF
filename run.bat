@echo off
REM Sync_B4_PowerOFF 실행 (더블클릭용) — 콘솔 창 없이 팝업만 표시
cd /d "%~dp0"
start "" pythonw main.py %*
