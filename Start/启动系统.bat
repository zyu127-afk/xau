@echo off
setlocal
cd /d "%~dp0.."

powershell -NoProfile -ExecutionPolicy Bypass -File "Tools\start_system.ps1"
if errorlevel 1 (
  echo.
  echo [ERROR] GoldTradingSystem startup failed. Review the error above and Logs folder.
  pause
  exit /b 1
)

echo.
echo GoldTradingSystem started.
echo For a normal stop, run the stop script in Start folder.
echo Normal stop does not flatten MT5 positions; Guardian server SL/weekend protection remains in MT5.
