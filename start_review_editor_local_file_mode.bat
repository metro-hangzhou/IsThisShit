@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"
set "_ROOT=%CD%"
set "_PYTHON=%_ROOT%\.venv\Scripts\python.exe"
set "_SERVER_SCRIPT=%_ROOT%\scripts\run_review_editor_server.py"
set "_APP_DIR=%_ROOT%\apps\review-editor"
set "_SERVER_HOST=127.0.0.1"
set "_SERVER_PORT=43127"
set "_DIST_ENTRY=%_APP_DIR%\dist\index.html"
set "_BROWSER_PROFILE=%_ROOT%\.tmp\review_editor_browser_profile"
set "_BROWSER_EXE="

if not exist "%_PYTHON%" (
  echo Missing Python runtime: %_PYTHON%
  exit /b 1
)

if not exist "%_SERVER_SCRIPT%" (
  echo Missing review editor server script: %_SERVER_SCRIPT%
  exit /b 1
)

if not exist "%_APP_DIR%\package.json" (
  echo Missing review editor app directory: %_APP_DIR%
  exit /b 1
)

for %%P in (
  "C:\Program Files\Google\Chrome\Application\chrome.exe"
  "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
  "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
  "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
) do (
  if exist %%~P (
    set "_BROWSER_EXE=%%~P"
    goto :browser_found
  )
)

echo No Chrome/Edge runtime found. Install Chrome or Edge first.
exit /b 1

:browser_found
if not exist "%_BROWSER_PROFILE%" mkdir "%_BROWSER_PROFILE%" >nul 2>nul

if not exist "%_APP_DIR%\node_modules" (
  echo Installing frontend deps in %_APP_DIR%
  pushd "%_APP_DIR%"
  npm install
  if errorlevel 1 (
    popd
    echo Failed to install frontend dependencies.
    exit /b 1
  )
  popd
)

echo Building review editor for local-file mode...
pushd "%_APP_DIR%"
set "VITE_REVIEW_API_BASE=http://%_SERVER_HOST%:%_SERVER_PORT%"
npm run build
if errorlevel 1 (
  popd
  echo Failed to build frontend bundle.
  exit /b 1
)
popd

set "_SERVER_CMD=cd /d ""%_ROOT%"" && ""%_PYTHON%"" ""%_SERVER_SCRIPT%"" --host %_SERVER_HOST% --port %_SERVER_PORT%"
echo Starting review editor backend on http://%_SERVER_HOST%:%_SERVER_PORT%
start "Review Editor Backend" cmd.exe /k "%_SERVER_CMD%"

echo.
echo Opening dedicated local-file browser profile:
echo   %_BROWSER_EXE%
echo   %_DIST_ENTRY%
echo.
echo This profile is only for local review-editor testing.
start "Review Editor Local File Browser" "%_BROWSER_EXE%" ^
  --user-data-dir="%_BROWSER_PROFILE%" ^
  --disable-web-security ^
  --allow-file-access-from-files ^
  --disable-site-isolation-trials ^
  --new-window ^
  "%_DIST_ENTRY%"

exit /b 0
