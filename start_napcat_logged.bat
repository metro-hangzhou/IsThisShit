@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "NAPCAT_LAUNCHER=%~dp0NapCat\napcat\launcher-win10.bat"
if defined NAPCAT_LAUNCHER_OVERRIDE set "NAPCAT_LAUNCHER=%NAPCAT_LAUNCHER_OVERRIDE%"
set "NAPCAT_LOG_DIR=%~dp0state\napcat_logs"
for %%I in ("%NAPCAT_LAUNCHER%") do set "NAPCAT_LAUNCHER_DIR=%%~dpI"

if not exist "%NAPCAT_LAUNCHER%" (
  echo NapCat launcher not found:
  echo   %NAPCAT_LAUNCHER%
  pause
  exit /b 1
)

if /I "%NAPCAT_SKIP_ADMIN_CHECK%"=="1" goto admin_ready

net session >nul 2>&1
if %ERRORLEVEL% neq 0 (
  echo Requesting administrator mode for NapCat startup...
  powershell -NoProfile -Command "Start-Process 'cmd.exe' -ArgumentList '/c cd /d \"%cd%\" && \"%~f0\" %*' -Verb RunAs"
  exit /b 0
)

:admin_ready
if not exist "%NAPCAT_LOG_DIR%" mkdir "%NAPCAT_LOG_DIR%"
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "(Get-Date).ToString('yyyyMMdd_HHmmss')"`) do set "NAPCAT_LOG_STAMP=%%I"
set "NAPCAT_LOG_FILE=%NAPCAT_LOG_DIR%\napcat_%NAPCAT_LOG_STAMP%.log"
set "NAPCAT_LOG_POINTER=%NAPCAT_LOG_DIR%\latest.path"

> "%NAPCAT_LOG_POINTER%" echo %NAPCAT_LOG_FILE%
echo NapCat log: %NAPCAT_LOG_FILE%
>> "%NAPCAT_LOG_FILE%" echo [launcher] started=%DATE% %TIME% launcher=%NAPCAT_LAUNCHER%

pushd "%NAPCAT_LAUNCHER_DIR%"
call "%NAPCAT_LAUNCHER%" %* >> "%NAPCAT_LOG_FILE%" 2>&1
set "NAPCAT_EXIT_CODE=%ERRORLEVEL%"
popd

>> "%NAPCAT_LOG_FILE%" echo [launcher] exited=%DATE% %TIME% exit_code=%NAPCAT_EXIT_CODE%
if not "%NAPCAT_EXIT_CODE%"=="0" (
  echo NapCat launcher exited with code %NAPCAT_EXIT_CODE%.
  echo See log: %NAPCAT_LOG_FILE%
  pause
)
exit /b %NAPCAT_EXIT_CODE%
