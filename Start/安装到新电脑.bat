@echo off
setlocal
cd /d "%~dp0.."
echo ==========================================
echo GoldTradingSystem installer
echo ==========================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\Tools\install.ps1"
if errorlevel 1 (
  echo.
  echo [FAILED] Installation did not complete. Review the error above.
  pause
  exit /b 1
)
echo.
echo [OK] Automated installation stage completed.
echo Next: follow Docs\MANUAL_SETUP.md for MT5 / ATAS / Rithmic machine acceptance.
pause
