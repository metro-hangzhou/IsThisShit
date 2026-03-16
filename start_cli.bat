@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "_CLI_ARGS=%*"
set "_WT_EXE="

if /I "%~1"=="--launched-in-modern-host" goto strip_modern_host

if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe" (
  set "_WT_EXE=%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe"
) else (
  for /f "delims=" %%I in ('where wt 2^>nul') do (
    if not defined _WT_EXE set "_WT_EXE=%%~fI"
  )
)

if "%~1"=="" (
  if not defined WT_SESSION (
    if not defined TERM_PROGRAM (
      if not defined ConEmuPID (
        if /I not "%CLI_AUTO_WT%"=="0" (
          if defined _WT_EXE (
            start "" "!_WT_EXE!" -w 0 new-tab cmd.exe /k "\"%~dp0start_cli_modern_host.bat\""
            exit /b 0
          )
        )
      )
    )
  )
)

:run_cli
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app.py %_CLI_ARGS%
  set "exit_code=!errorlevel!"
  if "!exit_code!"=="0" exit /b 0
  echo CLI exited with code !exit_code!.
  pause
  exit /b !exit_code!
)

where py >nul 2>nul
if %errorlevel%==0 (
  py -3.13 app.py %_CLI_ARGS%
  set "exit_code=!errorlevel!"
  if "!exit_code!"=="0" exit /b 0
  echo CLI exited with code !exit_code!.
  pause
  exit /b !exit_code!
)

echo Failed to start local runtime.
echo Expected .venv\Scripts\python.exe or a local Python 3.13 launcher.
pause
exit /b 1

:strip_modern_host
shift
call set "_CLI_ARGS=%%1 %%2 %%3 %%4 %%5 %%6 %%7 %%8 %%9"
goto run_cli
