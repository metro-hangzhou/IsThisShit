@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"
set "_ROOT=%CD%"

set "_DRY_RUN=0"
if /I "%~1"=="--dry-run" set "_DRY_RUN=1"

set "_PYTHON=%_ROOT%\.venv\Scripts\python.exe"
set "_SERVER_SCRIPT=%_ROOT%\scripts\run_review_editor_server.py"
set "_APP_DIR=%_ROOT%\apps\review-editor"
set "_SERVER_HOST=127.0.0.1"
set "_SERVER_PORT=43127"
set "_FRONTEND_PORT=5174"

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

set "_SERVER_CMD=cd /d ""%_ROOT%"" && ""%_PYTHON%"" ""%_SERVER_SCRIPT%"" --host %_SERVER_HOST% --port %_SERVER_PORT%"
set "_FRONTEND_CMD=cd /d ""%_APP_DIR%"" && set ""VITE_REVIEW_API_BASE=http://%_SERVER_HOST%:%_SERVER_PORT%"" && npm run dev -- --host %_SERVER_HOST% --port %_FRONTEND_PORT%"

if "%_DRY_RUN%"=="1" (
  echo [dry-run] backend:
  echo cd /d "%_ROOT%" ^&^& "%_PYTHON%" "%_SERVER_SCRIPT%" --host %_SERVER_HOST% --port %_SERVER_PORT%
  echo.
  echo [dry-run] frontend:
  if not exist "%_APP_DIR%\node_modules" (
    echo cd /d "%_APP_DIR%" ^&^& npm install ^&^& set "VITE_REVIEW_API_BASE=http://%_SERVER_HOST%:%_SERVER_PORT%" ^&^& npm run dev -- --host %_SERVER_HOST% --port %_FRONTEND_PORT%
  ) else (
    echo cd /d "%_APP_DIR%" ^&^& set "VITE_REVIEW_API_BASE=http://%_SERVER_HOST%:%_SERVER_PORT%" ^&^& npm run dev -- --host %_SERVER_HOST% --port %_FRONTEND_PORT%
  )
  exit /b 0
)

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

echo Starting review editor backend on http://%_SERVER_HOST%:%_SERVER_PORT%
start "Review Editor Backend" cmd.exe /k "%_SERVER_CMD%"

echo Starting review editor frontend on http://%_SERVER_HOST%:%_FRONTEND_PORT%
start "Review Editor Frontend" cmd.exe /k "%_FRONTEND_CMD%"

echo.
echo Review editor launch requested.
echo Backend:  http://%_SERVER_HOST%:%_SERVER_PORT%
echo Frontend: http://%_SERVER_HOST%:%_FRONTEND_PORT%
exit /b 0
