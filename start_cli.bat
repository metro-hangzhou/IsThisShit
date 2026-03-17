@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "_CLI_ARGS=%*"
set "_WT_EXE="
set "_POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "_CLI_GIT_REMOTE=origin"
set "_CLI_GIT_BRANCH=main"

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
        if /I "%CLI_AUTO_WT%"=="1" (
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
call :close_existing_cli
call :update_main_branch
echo Starting CLI...
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app.py %_CLI_ARGS%
  set "exit_code=!errorlevel!"
  if "!exit_code!"=="0" exit /b 0
  echo CLI exited with code !exit_code!.
  pause
  exit /b !exit_code!
)

if exist "python_runtime\python.exe" (
  set "BUNDLE_ROOT=%cd%"
  set "SRC_PATH=!BUNDLE_ROOT!\src"
  set "SITE_PACKAGES=!BUNDLE_ROOT!\runtime_site_packages"
  set "PYTHONPATH=!SRC_PATH!;!SITE_PACKAGES!;!PYTHONPATH!"
  set "PATH=!BUNDLE_ROOT!\python_runtime;!PATH!"
  set "PYTHONHOME=!BUNDLE_ROOT!\python_runtime"
  "python_runtime\python.exe" -c "import typer,prompt_toolkit,httpx,orjson,pydantic,rich,qrcode,websockets" >nul 2>nul
  if not "!errorlevel!"=="0" (
    echo Bundled Python runtime found but bundled dependencies are incomplete.
    echo Expected runtime_site_packages to contain the minimal CLI dependency set.
    pause
    exit /b 1
  )
  "python_runtime\python.exe" app.py %_CLI_ARGS%
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
echo Expected one of the following:
echo   1. .venv\Scripts\python.exe
echo   2. bundled python_runtime\python.exe plus runtime_site_packages
echo   3. a local Python 3.13 launcher
pause
exit /b 1

:strip_modern_host
shift
call set "_CLI_ARGS=%%1 %%2 %%3 %%4 %%5 %%6 %%7 %%8 %%9"
goto run_cli

:close_existing_cli
if /I "%CLI_KILL_EXISTING%"=="0" goto :eof
if not exist "%_POWERSHELL%" goto :eof
if not exist "%~dp0close_existing_cli.ps1" goto :eof
"%_POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0close_existing_cli.ps1" -RepoPath "%cd%" >nul 2>nul
goto :eof

:update_main_branch
if /I "%CLI_SKIP_GIT_UPDATE%"=="1" goto :eof
if not exist ".git" goto :eof
where git >nul 2>nul
if errorlevel 1 goto :eof
set "_CURRENT_BRANCH="
for /f "usebackq delims=" %%I in (`git branch --show-current 2^>nul`) do set "_CURRENT_BRANCH=%%I"
if /I not "!_CURRENT_BRANCH!"=="%_CLI_GIT_BRANCH%" goto :eof
echo Checking for updates...
git fetch --quiet %_CLI_GIT_REMOTE% %_CLI_GIT_BRANCH%
if errorlevel 1 (
  echo Git update check skipped. Continuing with local files.
  goto :eof
)
set "_LOCAL_HEAD="
set "_REMOTE_HEAD="
for /f "usebackq delims=" %%I in (`git rev-parse HEAD 2^>nul`) do set "_LOCAL_HEAD=%%I"
for /f "usebackq delims=" %%I in (`git rev-parse FETCH_HEAD 2^>nul`) do set "_REMOTE_HEAD=%%I"
if not defined _LOCAL_HEAD goto :eof
if not defined _REMOTE_HEAD goto :eof
if /I "!_LOCAL_HEAD!"=="!_REMOTE_HEAD!" (
  echo Already up to date.
  goto :eof
)
echo Update found. Fast-forwarding %_CLI_GIT_BRANCH%...
git pull --ff-only --no-rebase %_CLI_GIT_REMOTE% %_CLI_GIT_BRANCH%
if errorlevel 1 (
  echo Git update failed. Continuing with local files.
) else (
  echo Updated to latest %_CLI_GIT_BRANCH%.
)
goto :eof
