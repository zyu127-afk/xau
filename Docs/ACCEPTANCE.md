# V1 验收清单

状态含义：`[x]` 可由仓库自动测试覆盖；`[ ]` 需要 Windows/MT5/ATAS/Rithmic 实机联调。

- [ ] 识别当前 MT5 账户。
- [x] Guardian 直接使用 `_Symbol`，不写死 XAUUSD。
- [ ] 识别当前 ATAS 图表合约并处理 instrument_changed。
- [ ] ATAS 合约切换不导致系统崩溃。
- [ ] 获取真实 MT5 行情。
- [ ] 获取真实 ATAS 订单流。
- [x] GC↔MT5 滚动线性映射核心算法。
- [ ] 实际 OpenAI-compatible / DeepSeek 调用（需用户 API 配置）。
- [x] AI 客户端异步设计，不属于 Guardian 线程。
- [x] Snapshot / STALE 规则单元测试。
- [ ] 模拟开仓执行。
- [ ] 平仓执行。
- [ ] 修改服务器 SL。
- [ ] 撤销挂单。
- [x] Python 逻辑层最多 Position A/B 两仓。
- [ ] Hedging/Netting 在真实 MT5 账户联调。
- [ ] 周五实际 Session 的停止新仓/撤单/清仓实测。
- [ ] Python 崩溃时 Guardian 实机保护验证。
- [ ] ATAS 断线降级实测。
- [ ] AI 断线降级实测。
- [x] Dashboard 骨架和状态 API。
- [x] 分日志设计与 API Key 日志脱敏器。
- [x] SQLite 表结构。
- [x] MFE/MAE 逻辑单元测试。
- [x] NoTradeEvents 数据结构。
- [x] 90 天滚动清理且 Trades 不被删除的单元测试。
- [x] 相对路径配置。
- [ ] 新电脑完整安装脚本端到端实测。
- [ ] 最终 Dev/Portable ZIP 构建与验收。
