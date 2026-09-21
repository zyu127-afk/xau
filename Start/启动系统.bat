@echo off
setlocal
cd /d "%~dp0.."

set "PY="
if exist "Runtime\python\Scripts\python.exe" set "PY=Runtime\python\Scripts\python.exe"
if not defined PY if exist "Runtime\python\python.exe" set "PY=Runtime\python\python.exe"
if not defined PY set "PY=python"

"%PY%" -c "import yaml,httpx,fastapi,uvicorn" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python 运行环境未准备完成。
  echo 请先运行 Start\安装到新电脑.bat
  pause
  exit /b 1
)

if exist "Runtime\control.json" del /q "Runtime\control.json" >nul 2>&1

start "GoldTrading Dashboard" "%PY%" -m uvicorn UI.dashboard:app --host 127.0.0.1 --port 17840
timeout /t 1 /nobreak >nul
start "GoldTrading Engine" "%PY%" -m Engine.goldtrading.main
timeout /t 1 /nobreak >nul
start "" http://127.0.0.1:17840

echo GoldTradingSystem 已启动。
echo 关闭这个窗口不会自动平掉 MT5 仓位；Guardian 的服务器 SL / 周末保护仍由 MT5 执行。
