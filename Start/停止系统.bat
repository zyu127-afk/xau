@echo off
setlocal
cd /d "%~dp0.."

powershell -NoProfile -ExecutionPolicy Bypass -File "Tools\stop_system.ps1"
if errorlevel 1 (
  echo.
  echo [ERROR] GoldTradingSystem stop flow failed. Review the message above.
  pause
  exit /b 1
)

echo.
echo Local Engine / Dashboard stopped.
echo MT5 Guardian remains attached; a normal stop does not flatten existing positions.
pause
