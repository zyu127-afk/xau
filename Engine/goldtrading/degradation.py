from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DegradationState:
    level: int
    name: str
    allow_new_ai_trades: bool
    allow_local_structure_analysis: bool
    protect_existing_positions: bool
    reason: str


def classify_degradation(*, python_alive: bool = True, mt5_alive: bool, atas_health: str, ai_health: str) -> DegradationState:
    if not python_alive:
        return DegradationState(5, "GUARDIAN_ONLY", False, False, True, "Python完全失联，Guardian独立保护已有仓位")
    atas_ok = atas_health == "HEALTHY"
    ai_ok = ai_health == "HEALTHY"
    ai_slow = ai_health == "SLOW"
    if mt5_alive and atas_ok and ai_ok:
        return DegradationState(0, "FULL", True, True, True, "MT5 + ATAS + AI全部正常")
    if mt5_alive and atas_ok and ai_slow:
        return DegradationState(1, "AI_SLOW", True, True, True, "AI较慢，本地服务继续运行，AI结果仍需STALE验证")
    if mt5_alive and atas_ok and ai_health in {"OFFLINE", "TIMEOUT", "RATE_LIMIT", "SERVER_ERROR"}:
        return DegradationState(2, "AI_OFFLINE", False, True, True, "停止AI驱动的新判断，已有仓继续本地保护")
    if mt5_alive and not atas_ok and ai_health not in {"OFFLINE", "TIMEOUT", "RATE_LIMIT", "SERVER_ERROR"}:
        return DegradationState(3, "ATAS_OFFLINE", False, True, True, "ATAS离线，MT5结构继续运行，订单流降级")
    if mt5_alive and not atas_ok:
        return DegradationState(4, "LOCAL_MT5_ONLY", False, True, True, "ATAS与AI不可用，仅保留MT5结构与已有仓管理")
    return DegradationState(4, "MT5_OFFLINE", False, False, False, "MT5 Guardian未连接，禁止一切新执行")
