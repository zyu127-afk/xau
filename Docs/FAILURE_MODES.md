# 系统降级与故障隔离

系统按 V1 需求显式维护 Level 0~5：

- Level 0：MT5 + ATAS + AI 全部正常。
- Level 1：AI 慢，本地运行不中断；返回结果仍必须重新做 Snapshot/STALE 检查。
- Level 2：AI 离线，停止 AI 驱动的新判断；已有仓继续保护。
- Level 3：ATAS 离线，MT5 结构分析继续，订单流标记为降级。
- Level 4：ATAS + AI 都离线，仅保留 MT5、服务器 SL、平仓、周末保护和已有仓管理。
- Level 5：Python 完全失联，MT5 Guardian 独立承担已有仓保护。

任何增强组件的异常都不能解除 Guardian 已经建立的服务器 SL。Python 进程退出也不自动平掉仓位；正常退出和紧急退出是不同操作。
