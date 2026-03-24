@echo off
setlocal
cd /d "%~dp0"

echo ==============================
echo IZI AUTO START
echo ==============================

echo [1/5] Starting Backend :8000
start "IZI_BACKEND" cmd /k ^
  "cd backend && ..\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload"

echo Waiting for backend to be ready...

:WAIT_BACKEND
timeout /t 1 /nobreak >nul
netstat -ano | findstr ":8000" >nul
if errorlevel 1 goto WAIT_BACKEND

echo Backend is up.

timeout /t 2 /nobreak >nul

echo [2/5] Starting Chrome Debug :9222
start "IZI_CHROME_DEBUG" ^
  "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir="C:\selenium\ChromeProfile"

echo Waiting for Chrome debug port to be ready...
timeout /t 5 /nobreak >nul

echo [3/5] Starting Monitor
start "IZI_MONITOR" cmd /k ^
  "cd backend && ..\venv\Scripts\python.exe -u pianos\automation\monitor.py"

echo [4/5] Starting Frontend :5173
start "IZI_FRONTEND" /min cmd /c ^
  "cd frontend && npm run dev -- --host 127.0.0.1 --port 5173"

timeout /t 3 /nobreak >nul

echo [5/5] Starting Electron
start "IZI_ELECTRON" cmd /c ^
  "cd electron && npm start"

echo ==============================
echo All services started.
echo ==============================
pause