@echo off
setlocal
cd /d "%~dp0.."

set "PY="
if exist "Runtime\python\python.exe" set "PY=Runtime\python\python.exe"
if not defined PY if exist "Runtime\python\Scripts\python.exe" set "PY=Runtime\python\Scripts\python.exe"
if not defined PY set "PY=python"

echo ======================================================
echo GoldTradingSystem 本机只读预检
echo 该步骤不会发送任何交易订单。
echo ======================================================

"%PY%" Tools\preflight.py --probe-mt5
if errorlevel 1 (
  echo.
  echo 预检发现问题，请保留 Runtime\acceptance-report.json。
) else (
  echo.
  echo 基础预检完成。
)

echo.
echo 正在生成脱敏诊断包（不会包含 API Key、secrets.local 或交易数据库）...
"%PY%" Tools\collect_diagnostics.py

echo.
echo 完成。报告位于 Runtime\acceptance-report.json
pause
