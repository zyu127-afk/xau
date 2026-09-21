from __future__ import annotations

from dataclasses import dataclass
from .models import PositionState
from .orderflow import OrderFlowAssessment


@dataclass(frozen=True, slots=True)
class ManagementAction:
    action: str
    reason: str
    proposed_sl: float | None = None


def manage_position(position: PositionState, current_price: float, structure_broken: bool,
                    orderflow: OrderFlowAssessment, next_zone: tuple[float, float] | None = None) -> ManagementAction:
    """Dynamic management without a fixed R multiple. Returned actions still require Guardian validation."""
    side = position.side.upper()
    against = (side == "BUY" and orderflow.score <= -1.5) or (side == "SELL" and orderflow.score >= 1.5)
    if structure_broken and against:
        return ManagementAction("EXIT", "结构破坏且订单流明显反向")
    favorable_move = (current_price - position.entry_price) if side == "BUY" else (position.entry_price - current_price)
    giveback = max(0.0, position.mfe - max(0.0, favorable_move))
    if position.mfe > 0 and giveback >= position.mfe * 0.55 and against:
        return ManagementAction("EXIT", "MFE明显回吐且订单流反向")
    if next_zone is not None:
        low, high = next_zone
        near_zone = low <= current_price <= high
        if near_zone and against:
            return ManagementAction("EXIT", "到达下一关键区域且动能/订单流衰减")
    if position.mfe > 0 and giveback >= position.mfe * 0.35:
        if side == "BUY":
            candidate = max(position.current_sl, position.entry_price)
        else:
            candidate = min(position.current_sl, position.entry_price) if position.current_sl > 0 else position.entry_price
        return ManagementAction("TIGHTEN", "利润出现明显回吐，收紧结构保护", candidate)
    return ManagementAction("HOLD", "结构与订单流尚未给出退出条件")
