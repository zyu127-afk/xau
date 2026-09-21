from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from .breakout import BreakoutAssessment, BreakoutVerdict
from .models import Bias, MarketRegime
from .orderflow import OrderFlowAssessment
from .potential_zones import PotentialZone, ZoneStatus
from .structure import MarketStructureState


class TradeMode(str, Enum):
    TREND_PULLBACK = "TREND_PULLBACK"
    BREAKOUT_RETEST = "BREAKOUT_RETEST"
    EXTREME_REVERSAL = "EXTREME_REVERSAL"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class ModeAssessment:
    mode: TradeMode
    side: str
    quality: float
    ready: bool
    evidence: tuple[str, ...]


def assess_modes(structure: MarketStructureState, potentials: list[PotentialZone], breakout: BreakoutAssessment,
                 orderflow: OrderFlowAssessment) -> list[ModeAssessment]:
    results: list[ModeAssessment] = []
    entered_buy = any(x.side == "BUY" and x.status in {ZoneStatus.ENTERED, ZoneStatus.WAITING, ZoneStatus.TRIGGERED} for x in potentials)
    entered_sell = any(x.side == "SELL" and x.status in {ZoneStatus.ENTERED, ZoneStatus.WAITING, ZoneStatus.TRIGGERED} for x in potentials)
    if structure.regime in {MarketRegime.TREND, MarketRegime.EXTREME_TREND}:
        if structure.bias is Bias.LONG:
            ev = ["大周期多头结构"]
            if entered_buy: ev.append("价格进入关键支撑/回调区")
            if orderflow.score >= 0.45: ev.append("买方订单流重新增强")
            results.append(ModeAssessment(TradeMode.TREND_PULLBACK, "BUY", min(1.0, 0.35+0.25*entered_buy+0.40*(orderflow.score>=0.45)), entered_buy and orderflow.score>=0.45, tuple(ev)))
        elif structure.bias is Bias.SHORT:
            ev = ["大周期空头结构"]
            if entered_sell: ev.append("价格进入关键阻力/回调区")
            if orderflow.score <= -0.45: ev.append("卖方订单流重新增强")
            results.append(ModeAssessment(TradeMode.TREND_PULLBACK, "SELL", min(1.0, 0.35+0.25*entered_sell+0.40*(orderflow.score<=-0.45)), entered_sell and orderflow.score<=-0.45, tuple(ev)))
    if breakout.verdict is BreakoutVerdict.TRUE:
        direction_side = "BUY" if breakout.direction == "UP" else "SELL"
        flow_ok = orderflow.score >= 0.45 if direction_side == "BUY" else orderflow.score <= -0.45
        results.append(ModeAssessment(TradeMode.BREAKOUT_RETEST, direction_side, 0.55+0.35*flow_ok, bool(flow_ok), (breakout.reason, orderflow.label)))
    # Extreme reversal is intentionally strict: key-zone contact + opposing exhaustion/absorption evidence.
    if entered_buy and orderflow.score >= 1.5 and structure.regime in {MarketRegime.RANGE, MarketRegime.TRANSITION}:
        results.append(ModeAssessment(TradeMode.EXTREME_REVERSAL, "BUY", 0.80, True, ("关键支撑区域", orderflow.label, *orderflow.evidence[:3])))
    if entered_sell and orderflow.score <= -1.5 and structure.regime in {MarketRegime.RANGE, MarketRegime.TRANSITION}:
        results.append(ModeAssessment(TradeMode.EXTREME_REVERSAL, "SELL", 0.80, True, ("关键阻力区域", orderflow.label, *orderflow.evidence[:3])))
    return results or [ModeAssessment(TradeMode.NONE, "NEUTRAL", 0.0, False, ("当前没有满足三种核心交易模式",))]
