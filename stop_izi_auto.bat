@echo off
echo ==============================
echo Stopping IZI AUTO
echo ==============================

REM Backend (Django :8000)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
  echo Killing backend PID %%a
  taskkill /PID %%a /F >nul 2>&1
)

REM Frontend (Vite :5173)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do (
  echo Killing frontend PID %%a
  taskkill /PID %%a /F >nul 2>&1
)

REM Monitor (python)
taskkill /IM python.exe /F >nul 2>&1

REM Electron
taskkill /IM electron.exe /F >nul 2>&1

echo ==============================
echo All services stopped.
echo ==============================
pause
