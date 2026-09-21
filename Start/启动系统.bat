@echo off
setlocal
cd /d "%~dp0.."
if exist "Runtime\python\python.exe" (set "PY=Runtime\python\python.exe") else (set "PY=python")
start "GoldTrading Engine" "%PY%" -m Engine.goldtrading.main
start "GoldTrading Dashboard" "%PY%" -m uvicorn UI.dashboard:app --host 127.0.0.1 --port 17840
start "" http://127.0.0.1:17840
