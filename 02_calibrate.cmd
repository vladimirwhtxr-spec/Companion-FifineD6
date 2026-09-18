@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Run 01_install.cmd first.
 pause
 exit /b 1
)
echo Close FIFINE and old test windows. Reconnect D6. Companion is not needed for calibration.
pause
.venv\Scripts\python.exe d6_bridge.py calibrate
pause
