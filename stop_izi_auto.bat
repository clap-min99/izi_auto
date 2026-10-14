@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_izi_auto.ps1"
set "STOP_RESULT=%ERRORLEVEL%"
pause
exit /b %STOP_RESULT%
