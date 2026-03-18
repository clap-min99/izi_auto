@echo off
setlocal ENABLEDELAYEDEXPANSION

cd /d "%~dp0"

set "ROOT=%cd%"
set "PID_FILE=%ROOT%\.izi_auto_pids.txt"

echo ==============================
echo Stopping IZI AUTO (Windows)
echo ==============================

if not exist "%PID_FILE%" (
  echo PID 파일이 없습니다. 이미 종료되었을 수 있습니다.
  exit /b 0
)

for /f "usebackq tokens=1,2 delims=:" %%A in ("%PID_FILE%") do (
  if /i not "%%A"=="# IZI AUTO PID FILE" (
    set "NAME=%%A"
    set "PID=%%B"
    if defined PID (
      tasklist /FI "PID eq !PID!" | findstr /I "!PID!" >nul
      if not errorlevel 1 (
        echo [STOP] !NAME! ^(!PID!^)
        taskkill /PID !PID! /T /F >nul 2>&1
      ) else (
        echo [SKIP] !NAME! ^(!PID!^): 이미 종료됨
      )
    )
  )
)

del /q "%PID_FILE%" >nul 2>&1
echo 모든 서비스 종료 요청 완료
exit /b 0
