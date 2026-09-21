@echo off
setlocal
cd /d "%~dp0.."

set "PY="
if exist "Runtime\python\python.exe" set "PY=Runtime\python\python.exe"
if not defined PY if exist "Runtime\python\Scripts\python.exe" set "PY=Runtime\python\Scripts\python.exe"
if not defined PY set "PY=python"

echo ======================================================
echo GoldTradingSystem read-only machine preflight
echo This step does not submit any trading order.
echo ======================================================

"%PY%" Tools\preflight.py --probe-mt5
if errorlevel 1 (
  echo.
  echo Preflight found issues. Keep Runtime\acceptance-report.json.
) else (
  echo.
  echo Basic preflight completed.
)

echo.
echo Creating sanitized diagnostics package. API keys, secrets.local and trading database are excluded.
"%PY%" Tools\collect_diagnostics.py

echo.
echo Done. Report: Runtime\acceptance-report.json
pause
