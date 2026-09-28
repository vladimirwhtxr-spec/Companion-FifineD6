@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m unittest -v
if errorlevel 1 goto fail
echo Tests completed. Driver is NOT installed.
pause
exit /b 0
:fail
echo Setup or tests failed.
pause
exit /b 1
