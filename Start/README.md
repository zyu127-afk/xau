# Start scripts

Windows 正常操作入口全部位于本目录，并且只使用相对路径，便于整个 `GoldTradingSystem` 文件夹直接迁移。

- `安装到新电脑.bat`：首次部署/换机时运行，准备本机配置、Python、MT5 Guardian，并在检测到 ATAS 时尝试编译部署 Bridge。
- `本机验收.bat`：只读预检，不发送交易订单；生成脱敏验收报告与诊断包。
- `启动系统.bat`：正常启动 Engine + 中文 Dashboard。启动器会记录本系统自己的 PID/启动时间/Python 路径，供安全停止使用。
- `停止系统.bat`：正常停止本系统本地 Engine/Dashboard，只处理已记录且身份匹配的进程；不会使用 `taskkill /IM python.exe`，不会发送 `CLOSE_ALL`，不会因为正常停止自动平掉 MT5 已有仓位。

MT5 Guardian 运行在 MT5 内。正常停止 Engine/Dashboard 后，Guardian 与已下发到服务器端的 SL 不会被该停止脚本移除；周末保护仍由 Guardian 本地安全逻辑负责。

需要立即平掉系统仓位时，应使用 Dashboard 中明确的“紧急平仓”操作；它与 `停止系统.bat` 是两个不同动作。
