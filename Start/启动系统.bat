@echo off
setlocal
cd /d "%~dp0.."

powershell -NoProfile -ExecutionPolicy Bypass -File "Tools\start_system.ps1"
if errorlevel 1 (
  echo.
  echo [ERROR] GoldTradingSystem 启动失败。请查看上面的错误和 Logs 目录。
  pause
  exit /b 1
)

echo.
echo GoldTradingSystem 已启动。
echo 正常停止请双击 Start\停止系统.bat。
echo 正常停止不会自动平掉 MT5 仓位；Guardian 的服务器 SL / 周末保护仍由 MT5 执行。
