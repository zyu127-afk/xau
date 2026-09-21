# GoldTradingSystem — 最终实机配置

仓库能够自动完成的代码、配置模板、部署脚本和测试均保存在项目主目录。以下步骤必须在实际 Windows + MT5 + ATAS/Rithmic 环境完成，不能用模拟结果代替。

## 1. 新电脑安装

1. 将整个 `GoldTradingSystem` 文件夹复制到任意本地磁盘。
2. 双击 `Start/安装到新电脑.bat`。
3. 如果检测到多个 MT5，选择实际要交易的 MT5 实例。
4. 安装器会生成本机专用 `Config/paths.yaml`、准备 `Config/config.yaml` 与 `Config/secrets.local`、部署 Guardian 源码并尝试 MetaEditor 编译。
5. 如果检测到 ATAS，安装器会自动寻找本机 `ATAS.Indicators.dll` / `ATAS.DataFeedsCore.dll`，尝试匹配 .NET 8/10 编译 SDK Bridge，并且只有真实编译成功后才部署 DLL。
6. Portable 包直接使用项目内嵌 Python；Dev 包若没有项目 Python，则安装器会准备运行环境。

个人路径、真实 API Key、数据库和日志不应提交到 GitHub。

## 2. MT5 Guardian

1. 启动所选择的 MT5 模拟账户。
2. 检查 `Runtime/mt5-binding.json`；`ex5_exists=true` 才表示安装器实际生成过 EX5。若没有，则在 MetaEditor 打开部署后的 `MQL5/Experts/GoldTradingSystem/GoldTradingGuardian.mq5` 并确认 0 errors。
3. 把 Guardian 挂到实际要交易的黄金图表。系统使用当前 `_Symbol`，不要把图表名称写死为 XAUUSD。
4. 开启 Algo Trading。
5. 在 MT5 的 Expert Advisors / 网络或 Socket 许可中允许本机 `127.0.0.1` / `localhost`（Engine 默认端口 17832）。
6. EA 参数保持 `InpMaxLogicalPositions=2`；手数、Spread 上限和周末提前量按账户实际情况设置。
7. 观察 MT5 HUD 是否显示当前品种、Bid/Ask、市场状态、ATAS、AI、持仓数量与系统状态。

## 3. ATAS + Rithmic Paper

1. 启动 ATAS，并连接 Rithmic Paper/模拟环境。
2. 打开当前真正要采集的 GC 黄金期货合约图表。不要在代码里固定月份合约。
3. 检查 `Runtime/atas-binding.json`。`deployed=true` 且 `bridge_dll_exists_now=true` 表示本机 SDK Bridge 已真实编译并部署；若未完成，重新运行 `Tools/deploy_atas.ps1`，失败时查看 `Logs/atas_sdk_build_*.log`。不要手工复制未验证 DLL。
4. 在当前 GC 图表中加载 `GoldTradingSystem DataBridge` 指标/Bridge。DataBridge 必须从当前图表读取 instrument；切换合约时必须发出 `instrument_changed`。
5. 默认 `Config/config.yaml -> atas.require_mbo: false`，ATAS 指标端 `EnableMbo=false`。只有 `SubscribeMarketByOrderData()` 在当前 Rithmic 权限下真正成功后，才允许启用 MBO；否则 order-id/queue/replenishment/order_count 等 MBO 专属字段保持 `null`/缺失，绝不伪造。
6. DataBridge 只发送订单流数据到 `127.0.0.1:17831`，不得直接向 MT5 下单。

## 4. DeepSeek / OpenAI-compatible API

编辑本机 `Config/config.yaml`：

- `ai.base_url`
- `ai.model`
- `ai.timeout_seconds`
- `ai.retry`
- `ai.max_tokens`
- `ai.temperature`
- `ai.proxy`（需要时）

真实 Key 只写入 `Config/secrets.local`：

```text
API_KEY=你的真实Key
```

不要把 Key 发到 GitHub、日志、Dashboard 或普通备份。

## 5. 启动、只读预检与正常停止

先双击：

`Start/本机验收.bat`

它只做依赖、绑定、端口与可选 MT5 只读连接检查，不发送订单；结果写入 `Runtime/acceptance-report.json`，报告不包含 API Key、MT5 登录号或完整本机安装路径。

再双击：

`Start/启动系统.bat`

随后浏览器会打开本机中文 Dashboard。正常情况下应逐步看到：

- MT5 HEALTHY
- ATAS HEALTHY
- Rithmic CONNECTED
- Mapping 从 WARMING_UP 进入 HEALTHY
- AI 根据配置进入 HEALTHY/SLOW 或其他明确状态

正常结束本地系统时，双击：

`Start/停止系统.bat`

该脚本先请求 Engine 正常退出，再只停止 `Runtime/processes.json` 中由本系统启动且 PID、启动时间、Python 路径仍匹配的 Engine/Dashboard 进程。它不会广泛结束其他 Python 进程，也不会发送 `CLOSE_ALL`，因此正常停止不会自动平掉 MT5 已有仓位。

正常停止后，MT5 内的 Guardian 不会被该脚本卸载，已有服务器 SL 与 Guardian 本地周末保护继续存在。需要立即平掉系统仓位时，必须使用 Dashboard 中明确的“紧急平仓”操作；不要把“停止系统”和“紧急平仓”视为同一个动作。

## 6. 模拟盘验收顺序

必须先在 MT5 Demo + Rithmic Paper 完成：

1. 当前 MT5 账户和当前图表品种识别。
2. Hedging / Netting 实际账户模式识别。
3. 当前 ATAS 合约识别与合约切换。
4. GC↔MT5 映射预热、质量、合约切换后重建。
5. Trades/DOM/Delta/CVD/Footprint/快事件流入。
6. DeepSeek 请求、超时和 STALE 丢弃。
7. Position A / B 模拟开仓、真实服务器 SL、修改 SL、平仓、撤单。
8. AI Sleep 和“暂停新开仓”只禁止新仓，不破坏已有仓保护。
9. 运行中执行 `Start/停止系统.bat`，确认 Engine/Dashboard 正常停止、其他 Python 不受影响、已有 MT5 仓位不因正常停止被平掉。
10. Python 强制结束后，已有仓仍由 Guardian + 服务器 SL 保护。
11. ATAS/Rithmic 断开后，已有仓仍可平仓/改 SL/执行周末保护。
12. 周五真实 Session 前进入本地周末保护，撤单、平掉系统仓位，并确认 Positions=0、Orders=0。
13. Dashboard、MT5 HUD、日志、SQLite、MFE/MAE、NO TRADE、复盘记录一致。
14. 把整个项目复制到另一个本地路径，再跑一次安装器/预检/启动/停止，确认所有配置和运行路径仍为相对/本机生成。

全部模拟盘项目通过后，才进入下一阶段。仓库代码或 CI 通过不能替代这些实机验收。
