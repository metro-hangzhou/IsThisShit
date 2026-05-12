@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"
set "_ROOT=%CD%"
set "_START_LOCAL_FILE=%_ROOT%\start_review_editor_local_file_mode.bat"
set "_BACKEND_PORT=43127"
set "_FRONTEND_PORT=5174"

if not exist "%_START_LOCAL_FILE%" (
  echo Missing local file launcher: %_START_LOCAL_FILE%
  exit /b 1
)

taskkill /F /FI "WINDOWTITLE eq Review Editor Backend" >nul 2>nul
taskkill /F /FI "WINDOWTITLE eq Review Editor Frontend" >nul 2>nul
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":%_BACKEND_PORT% .*LISTENING"') do (
  taskkill /F /PID %%P >nul 2>nul
)
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":%_FRONTEND_PORT% .*LISTENING"') do (
  taskkill /F /PID %%P >nul 2>nul
)

call "%_START_LOCAL_FILE%"
exit /b 0
