# GoldTradingSystem

黄金日内 AI 自动交易系统 V1（全新开发母本）。

> 当前阶段：`0.21.0-dev / paper-integration-pending`。仓库侧核心实现与自动测试持续收敛；真实 MT5 / ATAS / Rithmic / DeepSeek 联调必须在用户本机模拟环境完成，不能用伪造数据冒充验收。

## 核心架构

- **MT5 Guardian**：交易执行器 + 最后一层本地风控；Guardian 拥有最终执行权。
- **ATAS DataBridge**：Rithmic 黄金期货订单流传感器；不直接向 MT5 下单。
- **Python Engine**：数据融合、GC↔MT5 映射、结构/订单流、决策、Position A/B、动态管理、历史与复盘。
- **AI**：OpenAI-compatible / DeepSeek 高级分析层；异步、可超时、结果必须经过 Snapshot / STALE 复核。
- **UI**：完整中文 Dashboard + MT5 精简 HUD。

## 不可破坏的安全原则

- 每笔成交必须存在真实服务器 SL；开仓后 Guardian 会再次验证。
- 周末保护由 Guardian 根据当前 `_Symbol` 的星期五真实交易 Session 本地执行。
- Python / AI / ATAS / Rithmic 异常不能让已有仓位失去最基本保护。
- Guardian 本地重复校验交易权限、手数、保证金、Spread、最大两仓、有效期、价格区域和重复命令。
- Netting 账户内部仍保存 Entry A / Entry B；共享服务器净仓采用 fail-safe 服务器 SL，逻辑 SL/TP 由 Guardian 独立跟踪。
- AI Sleep / 暂停新开仓不会停止行情记录、Dashboard、已有仓管理或周末保护。
- API Key 不写入源码、GitHub、日志、Dashboard 或普通备份。
- 所有开仓、拒绝、管理、退出和 NO TRADE 都应可审计、可复盘。
- 先完成 MT5 Demo + ATAS/Rithmic Paper 验收，再考虑真实账户。

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

所有平台专用路径只写入本机 `Config/paths.yaml`；主源码保持相对路径。

## 新电脑

1. 复制整个项目文件夹到任意本地磁盘。
2. 双击 `Start/安装到新电脑.bat`。
3. 安装器检测并选择 MT5、生成本机路径配置、部署 Guardian，并在找到 MetaEditor 时尝试真实编译。
4. 安装器检测到 ATAS 后，会自动尝试使用本机 `ATAS.Indicators.dll` / `ATAS.DataFeedsCore.dll` 编译并部署 SDK Bridge；失败时只记录/提示，不部署未验证 DLL。
5. Portable 包已经包含项目内嵌 Python；Dev 包在没有项目 Python 时由安装器准备运行环境。
6. 按 `Docs/MANUAL_SETUP.md` 完成 MT5 Socket、ATAS 图表加载、Rithmic Paper、DeepSeek 和模拟盘验收。
7. 双击 `Start/启动系统.bat`。

## Dashboard 控制

Dashboard 仅绑定 `127.0.0.1`，提供：

- AI Sleep
- 暂停 / 恢复新开仓
- 正常停止 Engine（**不会自动误平已有仓**）
- 明确确认后的紧急平仓

最终交易动作仍必须经过 Guardian。

## 交付包

`Tools/build_release.ps1` 生成：

- `GoldTradingSystem_Dev_<version>.zip`
- `GoldTradingSystem_Portable_<version>.zip`

Portable 包不包含真实 Key、数据库、日志、账户数据或用户绝对路径，并包含项目内嵌 Python。Windows CI 会实际解包 Portable 并验证关键 Python imports，而不是只检查 ZIP 是否生成。GitHub 的 `Build delivery packages` workflow 会产出可下载 artifact。

## 验收

- `Docs/ACCEPTANCE.md`：30 项 V1 验收矩阵。
- `Docs/MANUAL_SETUP.md`：只剩必须由真实平台完成的步骤。
- `Start/本机验收.bat`：只读预检，不发送订单；生成脱敏 `Runtime/acceptance-report.json`。

开发规格：`黄金日内 AI 交易系统 V1.0 完整总需求`。
