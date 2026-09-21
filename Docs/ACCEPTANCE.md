# GoldTradingSystem V1 验收矩阵

状态定义：

- `AUTO`：仓库/CI 可以自动验证。
- `LOCAL`：必须在用户真实 Windows + MT5/ATAS/Rithmic Paper 环境验证。
- `PASS` 只允许在真实证据存在时填写，不能用模拟字段替代。

| # | 验收项 | 类型 | 当前状态 |
|---|---|---|---|
| 1 | 识别当前 MT5 账户 | LOCAL | 待实机 |
| 2 | 识别当前 MT5 图表黄金品种 `_Symbol` | LOCAL | 代码完成；待实机 |
| 3 | 识别当前 ATAS 合约 | LOCAL | 待 SDK/Rithmic |
| 4 | ATAS 合约切换触发映射重建 | AUTO+LOCAL | 逻辑完成；待实机 |
| 5 | MT5 行情获取 | LOCAL | 待实机 |
| 6 | ATAS 订单流获取 | LOCAL | 待 SDK/Rithmic |
| 7 | GC↔MT5 映射 | AUTO+LOCAL | 数学/质量逻辑有测试；待真实同步流 |
| 8 | DeepSeek/OpenAI-compatible 调用 | LOCAL | 待本机 Key/Base URL/Model |
| 9 | API 超时不阻塞 Guardian | AUTO+LOCAL | 异步架构完成；待故障注入 |
| 10 | AI STALE 信号拒绝 | AUTO | 自动测试覆盖 |
| 11 | 模拟开仓 | LOCAL | 待 MT5 Demo |
| 12 | 平仓 | LOCAL | 待 MT5 Demo |
| 13 | 修改 SL | LOCAL | 待 MT5 Demo |
| 14 | 撤销挂单 | LOCAL | 待 MT5 Demo |
| 15 | 最大两个逻辑仓位 | AUTO+LOCAL | 逻辑有测试；待账户实测 |
| 16 | Hedging / Netting 兼容 | LOCAL | 待两类账户验证 |
| 17 | 周末强制清仓 | LOCAL | 待真实 Session/故障测试 |
| 18 | Python 崩溃后已有仓仍保护 | LOCAL | Guardian/服务器 SL 架构完成；待进程故障测试 |
| 19 | ATAS 断线时 MT5 仍工作 | LOCAL | 待断线测试 |
| 20 | AI 断线时已有仓仍工作 | AUTO+LOCAL | 逻辑完成；待实机 |
| 21 | Dashboard 状态正确 | AUTO+LOCAL | 接口/页面完成；待实机数据 |
| 22 | 日志完整且无 API Key | AUTO+LOCAL | Redaction 完成；待运行审计 |
| 23 | 历史记录完整 | AUTO+LOCAL | SQLite 结构完成；待长时运行 |
| 24 | MFE / MAE 正确 | AUTO+LOCAL | 逻辑测试覆盖；待成交验证 |
| 25 | NO TRADE 原因记录 | AUTO+LOCAL | 已实现；待真实行情审计 |
| 26 | 90 天滚动清理 | AUTO | 保留策略实现/测试 |
| 27 | 交易/复盘永久保存不被滚动清理 | AUTO | 独立永久表设计 |
| 28 | 整体文件夹换路径后仍工作 | LOCAL | 待 Windows 复制测试 |
| 29 | 新电脑安装重新连接 MT5/ATAS | LOCAL | 安装器已实现；待第二路径/电脑验证 |
| 30 | Dev / Portable ZIP | AUTO+LOCAL | 构建脚本提供；最终版本需生成并验证 |

## 放行规则

真实账户前，所有 `LOCAL` 项必须先在 **MT5 Demo + ATAS/Rithmic Paper** 环境完成并记录结果。任何涉及真实成交执行、服务器 SL、账户模式、交易 Session 或 ATAS SDK 的项目，都不能仅凭 GitHub Actions 标记为通过。
