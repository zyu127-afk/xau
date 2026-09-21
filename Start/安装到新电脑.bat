@echo off
setlocal
cd /d "%~dp0.."
echo ==========================================
echo GoldTradingSystem 新电脑安装器 bootstrap
echo ==========================================
if not exist Config\config.yaml copy Config\config.example.yaml Config\config.yaml >nul
if not exist Config\secrets.local copy Config\secrets.local.example Config\secrets.local >nul
echo [1/4] 配置模板已准备
echo [2/4] 请由 Tools\detect_platforms.ps1 检测 MT5/ATAS 实例
echo [3/4] 生产部署前必须编译 MT5 Guardian 与 ATAS Bridge
echo [4/4] 完成后运行 Start\启动系统.bat
pause
