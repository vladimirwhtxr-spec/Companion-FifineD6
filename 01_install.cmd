@echo off
setlocal
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto deps
where py >nul 2>nul
if not errorlevel 1 (
 py -3 -m venv .venv
) else (
 python -m venv .venv
)
if errorlevel 1 goto fail
:deps
.venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)"
if errorlevel 1 (
 echo Python 3.12 or newer is required. Install it and recreate .venv.
 goto fail
)
.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
if errorlevel 1 goto fail
echo Ready. Keep existing screen_map.json or run 02_calibrate.cmd, then 03_companion.vbs.
pause
exit /b 0
:fail
echo Installation failed. Send a screenshot of this window.
pause
exit /b 1
