@echo off
setlocal
cd /d "%~dp0.."

powershell -NoProfile -ExecutionPolicy Bypass -File "Tools\stop_system.ps1"
if errorlevel 1 (
  echo.
  echo [ERROR] GoldTradingSystem 停止流程遇到错误。请查看上面的提示。
  pause
  exit /b 1
)

echo.
echo 本地 Engine / Dashboard 已停止。
echo MT5 Guardian 不会被这个脚本卸载，已有仓位不会因为正常停止而自动平仓。
pause
