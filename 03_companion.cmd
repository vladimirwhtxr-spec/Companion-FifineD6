@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
 echo Run 01_install.cmd first.
 pause
 exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0d6_tray.py"
