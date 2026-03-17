@echo off
setlocal
cd /d "%~dp0"

set "_PYTHON="
if exist ".venv\Scripts\python.exe" set "_PYTHON=.venv\Scripts\python.exe"
if not defined _PYTHON if exist "python_runtime\python.exe" set "_PYTHON=python_runtime\python.exe"
if not defined _PYTHON set "_PYTHON=py -3.13"

echo Running targeted missing retest...
echo Repo: %cd%

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" targeted_missing_retest.py %*
  goto :end
)

if exist "python_runtime\python.exe" (
  "python_runtime\python.exe" targeted_missing_retest.py %*
  goto :end
)

py -3.13 targeted_missing_retest.py %*

:end
echo.
echo Done. Check state\targeted_retests\latest.path for the newest run directory.
pause
