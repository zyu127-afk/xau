# ATAS DataBridge

本目录分为两层：

- `GoldTradingDataBridge/`：不依赖 ATAS 专有程序集的核心层，负责 localhost JSONL、数据契约、健康状态和订单流派生；GitHub CI 可直接编译验证。
- `GoldTradingDataBridge.ATAS/`：真正引用用户本机 `ATAS.Indicators.dll` / `ATAS.DataFeedsCore.dll` 的官方 SDK 绑定层，读取当前图表合约的实时 Trade、BBO、DOM 与可选 MBO 数据。

`Tools/deploy_atas.ps1` 会针对本机 ATAS 程序集尝试 .NET 8/10 编译。只有编译成功才部署到 ATAS Indicators 目录，并写入 `Runtime/atas-binding.json`；失败时不复制未验证 DLL。

Bridge 仅作为传感器向 `127.0.0.1:17831` 发布数据，永远不直接向 MT5 下单。MBO 默认关闭，只有真实订阅成功后才发布 MBO 专属字段；没有权限时保持 null/缺失。
