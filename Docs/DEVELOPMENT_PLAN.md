# V1 开发阶段

本仓库按总需求的十二阶段推进，仓库根目录本身就是 `GoldTradingSystem/` 母本。

1. Portable 单根目录、Config、日志、SQLite、启动器、Guardian、中文 Dashboard 骨架。
2. ATAS DataBridge、Rithmic 原始数据、订单流事件采集。
3. GC ↔ MT5 Price Alignment。
4. MT5 多周期 Structure Engine。
5. Order Flow Engine。
6. OpenAI-compatible / DeepSeek API。
7. AI Snapshot / STALE 验证。
8. Decision Engine。
9. 动态持仓管理。
10. 完整中文 Dashboard + MT5 HUD。
11. 90 天历史与复盘系统。
12. MT5 模拟盘 + ATAS/Rithmic 模拟环境联调。

## 当前实现边界

Python 侧核心模型、SQLite、价格映射、结构、区域、订单流归纳、AI 客户端、STALE 校验、逻辑仓位 A/B、90 天清理、日报、中文 Web Dashboard 已建立第一版。MT5 Guardian 已建立本地硬风控骨架。ATAS Bridge 的 localhost 发布层和 SDK 边界已建立。

ATAS SDK 的实际回调绑定、Rithmic 权限字段、MT5 与 Python 的实时 IPC，以及真实/模拟终端编译联调必须在装有相应平台的 Windows 环境中完成，不能用伪造数据宣称已通过。
