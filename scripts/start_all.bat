@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%\.."

where py >nul 2>nul
if %errorlevel%==0 (
  py scripts\start_all.py %*
) else (
  python scripts\start_all.py %*
)

set "EXIT_CODE=%errorlevel%"
popd
exit /b %EXIT_CODE%
