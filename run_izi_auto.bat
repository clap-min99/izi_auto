@echo off
setlocal

REM ======================================
REM 프로젝트 루트
REM ======================================
cd /d "%~dp0"

echo ==============================
echo IZI AUTO START
echo ==============================

REM ======================================
REM 1. Django Backend (8000)
REM ======================================
echo [1/4] Starting Backend :8000
start "IZI_BACKEND" /min cmd /c ^
  "cd backend && ..\venv\Scripts\activate && python manage.py runserver 127.0.0.1:8000"

REM ======================================
REM 2. Backend 준비 대기 (포트 체크)
REM ======================================
echo Waiting for backend to be ready...

:WAIT_BACKEND
timeout /t 1 /nobreak >nul
netstat -ano | findstr :8000 >nul
if errorlevel 1 goto WAIT_BACKEND

echo Backend is up.

REM ======================================
REM 3. Monitor 실행
REM ======================================
echo [2/4] Starting Monitor
start "IZI_MONITOR" /min cmd /c ^
  "cd backend && ..\venv\Scripts\activate && python pianos\automation\monitor.py"

REM ======================================
REM 4. Frontend (5173)
REM ======================================
echo [3/4] Starting Frontend :5173
start "IZI_FRONTEND" /min cmd /c ^
  "cd frontend && npm run dev -- --host 127.0.0.1 --port 5173"

REM ======================================
REM 5. Electron
REM ======================================
timeout /t 3 /nobreak >nul
echo [4/4] Starting Electron
start "IZI_ELECTRON" cmd /c ^
  "cd electron && npm start"

echo ==============================
echo All services started.
echo ==============================
pause
