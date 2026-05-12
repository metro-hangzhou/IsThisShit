@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"
set "_ROOT=%CD%"
set "_START_SCRIPT=%_ROOT%\start_review_editor.bat"
set "_BACKEND_PORT=43127"
set "_FRONTEND_PORT=5174"
set "_DRY_RUN=0"

if /I "%~1"=="--dry-run" set "_DRY_RUN=1"

if not exist "%_START_SCRIPT%" (
  echo Missing start script: %_START_SCRIPT%
  exit /b 1
)

call :close_window "Review Editor Backend"
call :close_window "Review Editor Frontend"
call :kill_port %_BACKEND_PORT%
call :kill_port %_FRONTEND_PORT%

if "%_DRY_RUN%"=="1" (
  echo [dry-run] would restart via:
  echo call "%_START_SCRIPT%"
  exit /b 0
)

echo Restarting review editor...
call "%_START_SCRIPT%"
exit /b %errorlevel%

:close_window
set "_TITLE=%~1"
if "%_DRY_RUN%"=="1" (
  echo [dry-run] taskkill /F /FI "WINDOWTITLE eq %_TITLE%"
  goto :eof
)
taskkill /F /FI "WINDOWTITLE eq %_TITLE%" >nul 2>nul
goto :eof

:kill_port
set "_PORT=%~1"
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":%_PORT% .*LISTENING"') do (
  if "%_DRY_RUN%"=="1" (
    echo [dry-run] taskkill /F /PID %%P
  ) else (
    echo Releasing TCP port %_PORT% from PID %%P
    taskkill /F /PID %%P >nul 2>nul
  )
)
goto :eof
