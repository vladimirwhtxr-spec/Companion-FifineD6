@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0diagnose.ps1"
pause
