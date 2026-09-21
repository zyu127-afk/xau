# GoldTradingSystem

黄金日内 AI 自动交易系统（全新开发母本）。

## 核心架构

- MT5 Guardian：交易执行器 + 最后一层本地风控
- ATAS DataBridge：Rithmic 黄金期货订单流传感器
- Python Engine：数据融合、规则、决策、持仓管理与复盘
- AI：OpenAI-compatible / DeepSeek 高级分析层
- UI：中文 Dashboard + MT5 HUD

## 不可破坏的原则

- Guardian 拥有最终执行权
- AI / ATAS / Python 故障不能导致已有仓位失控
- 每笔成交必须存在真实服务器 SL
- 周末保护由 Guardian 本地硬执行
- AI 信号必须经过 Snapshot / STALE 时效验证
- API Key 不写入源码、日志或普通备份
- 所有交易决定必须可解释、可审计、可复盘
- 先完成模拟盘联调和验收，再考虑真实账户

## Portable 目录

```text
GoldTradingSystem/
  Start/
  MT5/
  ATAS/
  Engine/
  UI/
  AI/
  Config/
  Data/
  Logs/
  Backup/
  Runtime/
  Version/
  Tools/
  Docs/
  Tests/
```

开发规格：GoldTradingSystem V1.0 完整总需求。

本仓库内能自动化实现与测试的部分会直接实现；必须依赖本机 MT5 / ATAS / Rithmic / 经纪商环境的步骤集中记录在 `Docs/MANUAL_STEPS.md`。
