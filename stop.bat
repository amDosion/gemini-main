@echo off
rem ============================================================
rem  gemini-main one-click stop (Windows)
rem  Kills project-owned listeners on :21573 (node/vite) and
rem  :21574 (python/uvicorn), including their child process tree.
rem  Pass -Force to also kill unrelated processes on those ports.
rem ============================================================
setlocal
cd /d "%~dp0"

set "PSEXE="
where pwsh >nul 2>nul && set "PSEXE=pwsh"
if not defined PSEXE where powershell >nul 2>nul && set "PSEXE=powershell"
if not defined PSEXE (
  echo [ERROR] Neither pwsh nor powershell found in PATH.
  pause
  exit /b 1
)

"%PSEXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [ERROR] stop.ps1 exited with code %RC%. See messages above.
  echo.
  pause
)
endlocal
