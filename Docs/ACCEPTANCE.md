# GoldTradingSystem V1 验收矩阵

状态定义：

- `AUTO`：仓库/CI 可以自动验证。
- `LOCAL`：必须在用户真实 Windows + MT5/ATAS/Rithmic Paper 环境验证。
- `PASS` 只允许在真实证据存在时填写，不能用模拟字段替代。
- `AUTO PASS / LOCAL 待验`：仓库侧自动证据已通过，但仍存在不可替代的实机步骤。

| # | 验收项 | 类型 | 当前状态 |
|---|---|---|---|
| 1 | 识别当前 MT5 账户 | LOCAL | 待实机 |
| 2 | 识别当前 MT5 图表黄金品种 `_Symbol` | LOCAL | 代码完成；待实机 |
| 3 | 识别当前 ATAS 合约 | LOCAL | SDK 绑定完成；待本机编译/实时流 |
| 4 | ATAS 合约切换触发映射重建 | AUTO+LOCAL | AUTO PASS：重置逻辑/契约已测试；LOCAL 待实时切换 |
| 5 | MT5 行情获取 | LOCAL | 待实机 |
| 6 | ATAS 订单流获取 | LOCAL | SDK 回调已实现；待 Rithmic Paper 实时流 |
| 7 | GC↔MT5 映射 | AUTO+LOCAL | AUTO PASS：数学、质量、stale、合约重置有测试；LOCAL 待真实同步流 |
| 8 | DeepSeek/OpenAI-compatible 调用 | LOCAL | 待本机 Key/Base URL/Model |
| 9 | API 超时不阻塞 Guardian | AUTO+LOCAL | AUTO PASS：异步/超时/降级路径有测试；LOCAL 待进程故障注入 |
| 10 | AI STALE 信号拒绝 | AUTO | PASS：自动测试覆盖 |
| 11 | 模拟开仓 | LOCAL | 待 MT5 Demo |
| 12 | 平仓 | LOCAL | 待 MT5 Demo |
| 13 | 修改 SL | LOCAL | 待 MT5 Demo |
| 14 | 撤销挂单 | LOCAL | 待 MT5 Demo |
| 15 | 最大两个逻辑仓位 | AUTO+LOCAL | AUTO PASS：Position A/B 与 Guardian 安全契约测试；LOCAL 待账户实测 |
| 16 | Hedging / Netting 兼容 | LOCAL | 代码路径完成；待两类账户验证 |
| 17 | 周末强制清仓 | LOCAL | Guardian 按真实 Friday Session 实现并有源码安全契约；待真实 Session/故障测试 |
| 18 | Python 崩溃后已有仓仍保护 | LOCAL | Guardian/服务器 SL 架构完成并有安全契约；待进程故障测试 |
| 19 | ATAS 断线时 MT5 仍工作 | LOCAL | 待断线测试 |
| 20 | AI 断线时已有仓仍工作 | AUTO+LOCAL | AUTO PASS：降级逻辑有测试；LOCAL 待实机 |
| 21 | Dashboard 状态正确 | AUTO+LOCAL | AUTO：接口/安全测试通过；LOCAL 待真实数据一致性检查 |
| 22 | 日志完整且无 API Key | AUTO+LOCAL | AUTO PASS：secret hygiene + diagnostics redaction；LOCAL 待运行日志审计 |
| 23 | 历史记录完整 | AUTO+LOCAL | AUTO：SQLite/记录链测试通过；LOCAL 待长时运行 |
| 24 | MFE / MAE 正确 | AUTO+LOCAL | AUTO PASS：逻辑测试覆盖；LOCAL 待真实成交验证 |
| 25 | NO TRADE 原因记录 | AUTO+LOCAL | AUTO PASS：记录/去重测试覆盖；LOCAL 待真实行情审计 |
| 26 | 90 天滚动清理 | AUTO | PASS：保留策略自动测试覆盖 |
| 27 | 交易/复盘永久保存不被滚动清理 | AUTO | PASS：独立永久表与自动测试覆盖 |
| 28 | 整体文件夹换路径后仍工作 | LOCAL | 相对路径/安装器已实现；待 Windows 第二路径复制测试 |
| 29 | 新电脑安装重新连接 MT5/ATAS | LOCAL | 自动检测、MT5 部署/编译、ATAS SDK 编译链已实现；待目标电脑验证 |
| 30 | Dev / Portable ZIP | AUTO+LOCAL | AUTO PASS：Windows workflow 已真实生成约 30 MB artifact 并验证 Portable 内嵌 Python；LOCAL 待目标机解包安装/启动 |

## 当前自动证据

最新仓库侧 Python CI 已完成全部测试（当前为 79+，并继续随新增安全契约增长）；ATAS SDK-independent Core build 成功；Windows `Build delivery packages` 已真实产出 Dev/Portable artifact，而不是只验证脚本语法。

`Start/本机验收.bat` 为只读检查，不发送订单。它会读取 `Runtime/mt5-binding.json` / `Runtime/atas-binding.json`，确认 EX5/DLL 当前是否真实存在，并生成脱敏 `Runtime/acceptance-report.json`。

## 放行规则

真实账户前，所有 `LOCAL` 项必须先在 **MT5 Demo + ATAS/Rithmic Paper** 环境完成并记录结果。任何涉及真实成交执行、服务器 SL、账户模式、交易 Session、ATAS 专有 SDK、Rithmic 权限或真实 API 的项目，都不能仅凭 GitHub Actions 标记为通过。
