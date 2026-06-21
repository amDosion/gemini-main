@echo off
rem ============================================================
rem  gemini-main one-click start (Windows)
rem  Pure ASCII / no chcp so cmd.exe parses this file reliably.
rem  Console UTF-8 is set inside start.ps1 (Console.OutputEncoding),
rem  the two service terminals set their own codepage via cmd /k.
rem  Double-click to launch backend(:21574, venv) + frontend(:21573).
rem  Flags pass through, e.g.:
rem    start.bat -Background    (hidden windows, logs in .\logs\)
rem    start.bat -NoBrowser     (do not auto-open browser)
rem    start.bat -SkipChecks    (skip PostgreSQL/Redis probe)
rem    start.bat -Force         (start even if port is occupied)
rem ============================================================
setlocal
cd /d "%~dp0"

rem Prefer PowerShell 7 (pwsh) which reads UTF-8 reliably; fall back to
rem Windows PowerShell 5.1 (powershell) when pwsh is not installed.
set "PSEXE="
where pwsh >nul 2>nul && set "PSEXE=pwsh"
if not defined PSEXE where powershell >nul 2>nul && set "PSEXE=powershell"
if not defined PSEXE (
  echo [ERROR] Neither pwsh nor powershell found in PATH.
  pause
  exit /b 1
)

"%PSEXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
set "RC=%ERRORLEVEL%"

rem Only pause on failure so you can read the error; on success the
rem launcher window closes and leaves the two service terminals.
if not "%RC%"=="0" (
  echo.
  echo [ERROR] start.ps1 exited with code %RC%. See messages above.
  echo.
  pause
)
endlocal
