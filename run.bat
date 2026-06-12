@echo off
REM Sync_B4_PowerOFF 실행 (더블클릭용)
cd /d "%~dp0"
python main.py %*
pause
