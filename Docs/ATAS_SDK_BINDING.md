# ATAS SDK 绑定边界

`ATAS/GoldTradingDataBridge` 中可独立编译的代码只负责 localhost 发布协议、数据契约和故障隔离。真正读取 ATAS 当前图表、Rithmic 行情和订单流事件的 SDK 调用必须绑定用户安装的 ATAS SDK/程序集，因此不能在 GitHub Linux/Windows 通用 runner 上伪造通过。

生产绑定必须满足：

- 当前图表是什么黄金期货合约就读取什么合约，不写死 GC 月份。
- 合约变化发出 `instrument_changed` 并让 Python 重建 GC↔MT5 映射。
- 采集 Trades/Tick/Bid/Ask/DOM/Cumulative Trades/Delta/CVD/Footprint/Imbalance/Volume。
- 派生并记录大单、Sweep、Absorption、Exhaustion、Liquidity Pull/Stack、疑似 Iceberg、DOM 快速变化、Delta/Footprint 异常。
- MBO 未授权时 `mbo_available=false`，MBO/队列相关字段保持 null/缺失，绝不填造假值。
- Bridge 只能发数据，不能直接向 MT5 下单。
