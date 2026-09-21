# ATAS SDK 绑定与本机验证

仓库现在分为两层：

- `ATAS/GoldTradingDataBridge`：不依赖专有 ATAS 程序集的核心层，负责 localhost 发布协议、数据契约、健康状态和订单流派生；GitHub CI 会持续编译它。
- `ATAS/GoldTradingDataBridge.ATAS`：真正引用本机 `ATAS.Indicators.dll` / `ATAS.DataFeedsCore.dll` 的 SDK 绑定层。它继承 ATAS `Indicator`，从当前图表读取实时数据，再喂给核心层。

## 已实现的 SDK 回调

绑定层已经接入：

- 当前图表 `InstrumentInfo.Instrument`，不写死 GC 月份；
- `OnNewTrade`；
- `OnBestBidAskChanged`；
- `MarketDepthsChanged`；
- `OnMarketByOrdersChanged`；
- ATAS 官方 `SubscribeMarketByOrderData()` MBO 订阅；
- 图表合约变化后重新发送 `instrument_changed`；
- Bridge 只发布数据，永远不直接向 MT5 下单。

`Tools/deploy_atas.ps1` 会在用户电脑上寻找真实 `ATAS.Indicators.dll`，识别/尝试 .NET 8 或 .NET 10 目标，用本机 SDK 实际 `dotnet build`。只有编译成功才把 `GoldTradingDataBridge.ATAS.dll` 与核心 DLL 部署到 ATAS Indicators 目录，并写入 `Runtime/atas-binding.json`；失败时不会复制未验证二进制。

## MBO 原则

`EnableMbo` 默认 `false`。只有用户明确开启并且 ATAS/Rithmic 的 `SubscribeMarketByOrderData()` 真正订阅成功后，`mbo_available` 才会变成 true，才允许发布真实 MBO 字段。

没有 MBO 权限时：

- `mbo_available=false`；
- DOM 的 `order_count` 保持 null；
- replenishment/order-id/queue 等 MBO 专属信息保持 null/缺失；
- 不根据 MBP/DOM 聚合数据伪造任何逐单字段。

## 为什么仍然需要一次本机验证

GitHub Runner 没有用户安装的 ATAS 专有程序集、Rithmic Paper 会话和当前 GC 图表，因此它只能验证 SDK-independent core 与绑定源码契约。最终是否能针对用户当前 ATAS build 编译、加载、接收到 Rithmic 实时数据，只能在那台 Windows 机器上证明。

最终本机证据由：

1. `Tools/deploy_atas.ps1` 成功生成 `Runtime/atas-binding.json`；
2. `Start/本机验收.bat` 报告 `bindings.atas.deployed=true` 且 `bridge_dll_exists_now=true`；
3. ATAS 当前 GC 图表加载指标后，17831 出现实时 JSONL；
4. Python Dashboard 显示实际 ATAS 合约、订单流和映射预热/健康状态。

这些证据都通过后，才允许把 ATAS SDK/Rithmic 的 LOCAL 验收项标为 PASS。
