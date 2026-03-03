@echo off
setlocal ENABLEDELAYEDEXPANSION

cd /d "%~dp0"

set "ROOT=%cd%"
set "PID_FILE=%ROOT%\.izi_auto_pids.txt"
set "LOG_DIR=%ROOT%\.izi_auto_logs"

if exist "%PID_FILE%" (
  echo 이미 실행 중일 수 있습니다. stop_izi_auto.bat 를 먼저 실행하세요.
  exit /b 1
)

if not exist "%ROOT%\venv\Scripts\python.exe" (
  echo venv\Scripts\python.exe 를 찾을 수 없습니다. 가상환경을 먼저 준비하세요.
  exit /b 1
)

if not exist "%ROOT%\frontend\node_modules" (
  echo frontend\node_modules 가 없습니다. frontend 폴더에서 npm install 을 먼저 실행하세요.
  exit /b 1
)

if not exist "%ROOT%\electron\node_modules" (
  echo electron\node_modules 가 없습니다. electron 폴더에서 npm install 을 먼저 실행하세요.
  exit /b 1
)

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

> "%PID_FILE%" echo # IZI AUTO PID FILE

echo ==============================
echo IZI AUTO START (Windows)
echo ==============================

echo [1/4] BACKEND 시작 (터미널 표시)
call :start_service_visible BACKEND "%ROOT%\backend" "..\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000" "%LOG_DIR%\backend.log"
call :wait_backend

echo [2/4] MONITOR 시작 (터미널 표시)
call :start_service_visible MONITOR "%ROOT%\backend" "..\venv\Scripts\python.exe pianos\automation\monitor.py" "%LOG_DIR%\monitor.log"

echo [3/4] FRONTEND 시작 (백그라운드)
call :start_service_hidden FRONTEND "%ROOT%\frontend" "npm run dev -- --host 127.0.0.1 --port 5173" "%LOG_DIR%\frontend.log"

echo [4/4] ELECTRON 시작 (백그라운드)
call :start_service_hidden ELECTRON "%ROOT%\electron" "npm start" "%LOG_DIR%\electron.log"

echo.
echo 모든 서비스 실행 완료
echo - BACKEND, MONITOR 터미널만 표시됩니다.
echo - FRONTEND, ELECTRON 은 백그라운드로 실행됩니다.
echo - PID 파일: %PID_FILE%
echo - 로그 폴더: %LOG_DIR%
echo 중지하려면 stop_izi_auto.bat 실행
exit /b 0

:start_service_visible
set "NAME=%~1"
set "WORKDIR=%~2"
set "SERVICE_CMD=%~3"
set "LOG=%~4"

for /f %%P in ('powershell -NoProfile -Command "$windowTitle = 'IZI_%NAME%'; $inline = \"$Host.UI.RawUI.WindowTitle = '$windowTitle'; Set-Location -Path '%WORKDIR%'; %SERVICE_CMD% 2^>^&1 ^| Tee-Object -FilePath '%LOG%' -Append\"; $p = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoExit','-NoProfile','-Command',$inline -PassThru; $p.Id"') do set "PID=%%P"

if not defined PID (
  echo [FAIL] %NAME% 시작 실패
  exit /b 1
)

echo [OK] %NAME% started (PID: !PID!)
>> "%PID_FILE%" echo %NAME%:!PID!
set "PID="
exit /b 0

:start_service_hidden
set "NAME=%~1"
set "WORKDIR=%~2"
set "SERVICE_CMD=%~3"
set "LOG=%~4"

for /f %%P in ('powershell -NoProfile -Command "$cmdline = \"cd /d '%WORKDIR%' && %SERVICE_CMD% >> '%LOG%' 2^>^&1\"; $p = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c',$cmdline -WindowStyle Hidden -PassThru; $p.Id"') do set "PID=%%P"

if not defined PID (
  echo [FAIL] %NAME% 시작 실패
  exit /b 1
)

echo [OK] %NAME% started (PID: !PID!)
>> "%PID_FILE%" echo %NAME%:!PID!
set "PID="
exit /b 0

:wait_backend
echo Backend 준비 대기 중...
:WAIT_LOOP
timeout /t 1 /nobreak >nul
netstat -ano | findstr ":8000" >nul
if errorlevel 1 goto WAIT_LOOP
echo Backend is up.
exit /b 0
