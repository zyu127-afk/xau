from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from .structure import Bar
from .zones import PriceZone


class BreakoutVerdict(str, Enum):
    TRUE = "TRUE_BREAKOUT"
    FALSE = "FALSE_BREAKOUT"
    PENDING = "PENDING"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class BreakoutAssessment:
    verdict: BreakoutVerdict
    direction: str
    zone: PriceZone | None
    reason: str


def assess_breakout(bars: list[Bar], zones: list[PriceZone]) -> BreakoutAssessment:
    if len(bars) < 3 or not zones:
        return BreakoutAssessment(BreakoutVerdict.NONE, "NEUTRAL", None, "数据不足")
    prev2, prev, cur = bars[-3], bars[-2], bars[-1]
    candidates = sorted(zones, key=lambda z: min(abs(cur.close-z.low), abs(cur.close-z.high)))
    zone = candidates[0]
    body_ratio = cur.body / cur.range if cur.range > 0 else 0.0
    if zone.kind == "RESISTANCE":
        # Failed auction above resistance: traded outside but failed to close above it.
        if cur.high > zone.high and cur.close <= zone.high:
            return BreakoutAssessment(BreakoutVerdict.FALSE, "UP", zone, "上破阻力后收回区域内")
        if prev.close > zone.high and cur.close <= zone.high:
            return BreakoutAssessment(BreakoutVerdict.FALSE, "UP", zone, "前一根收在阻力外，随后重新跌回区域")
        if prev.close <= zone.high < cur.close:
            if body_ratio >= 0.50:
                return BreakoutAssessment(BreakoutVerdict.PENDING, "UP", zone, "实体突破阻力，等待接受新价格/回抽确认")
        if prev.close > zone.high and cur.close > zone.high:
            retest = cur.low <= zone.high and cur.close > zone.high
            reason = "突破后回抽阻力并重新站稳" if retest else "连续收盘接受阻力上方新价格"
            return BreakoutAssessment(BreakoutVerdict.TRUE, "UP", zone, reason)
    else:
        if cur.low < zone.low and cur.close >= zone.low:
            return BreakoutAssessment(BreakoutVerdict.FALSE, "DOWN", zone, "下破支撑后收回区域内")
        if prev.close < zone.low and cur.close >= zone.low:
            return BreakoutAssessment(BreakoutVerdict.FALSE, "DOWN", zone, "前一根收在支撑外，随后重新涨回区域")
        if prev.close >= zone.low > cur.close:
            if body_ratio >= 0.50:
                return BreakoutAssessment(BreakoutVerdict.PENDING, "DOWN", zone, "实体跌破支撑，等待接受新价格/回抽确认")
        if prev.close < zone.low and cur.close < zone.low:
            retest = cur.high >= zone.low and cur.close < zone.low
            reason = "跌破后回抽支撑并重新压回" if retest else "连续收盘接受支撑下方新价格"
            return BreakoutAssessment(BreakoutVerdict.TRUE, "DOWN", zone, reason)
    return BreakoutAssessment(BreakoutVerdict.NONE, "NEUTRAL", zone, "当前未发生关键区域突破")
