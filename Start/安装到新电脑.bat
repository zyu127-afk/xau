@echo off
setlocal
cd /d "%~dp0.."
echo ==========================================
echo GoldTradingSystem 新电脑安装器
echo ==========================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\Tools\install.ps1"
if errorlevel 1 (
  echo.
  echo [FAILED] 安装未完成，请查看上面的错误信息。
  pause
  exit /b 1
)
echo.
echo [OK] 自动安装阶段完成。
echo 下一步请按 Docs\MANUAL_SETUP.md 完成 MT5 / ATAS / Rithmic 实机步骤。
pause
