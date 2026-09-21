from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import mean
from typing import Iterable
from .models import MarketRegime, Bias


@dataclass(frozen=True, slots=True)
class Bar:
    ts: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def range(self) -> float:
        return max(0.0, self.high - self.low)

    @property
    def body(self) -> float:
        return abs(self.close - self.open)


@dataclass(frozen=True, slots=True)
class TimeframeStructure:
    timeframe: str
    direction: str
    last_high: float
    last_low: float
    atr: float
    impulse_score: float


@dataclass(frozen=True, slots=True)
class MarketStructureState:
    regime: MarketRegime
    bias: Bias
    structures: dict[str, TimeframeStructure]
    state_id: str
    reasons: tuple[str, ...]


def atr(bars: list[Bar], period: int = 14) -> float:
    if len(bars) < 2:
        return 0.0
    trs: list[float] = []
    for i in range(1, len(bars)):
        prev = bars[i - 1].close
        b = bars[i]
        trs.append(max(b.high - b.low, abs(b.high - prev), abs(b.low - prev)))
    values = trs[-period:]
    return mean(values) if values else 0.0


def _swing_points(bars: list[Bar], wing: int = 2) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    for i in range(wing, len(bars) - wing):
        b = bars[i]
        if all(b.high >= bars[j].high for j in range(i - wing, i + wing + 1) if j != i):
            highs.append((i, b.high))
        if all(b.low <= bars[j].low for j in range(i - wing, i + wing + 1) if j != i):
            lows.append((i, b.low))
    return highs, lows


def classify_timeframe(timeframe: str, bars: Iterable[Bar]) -> TimeframeStructure:
    data = list(bars)
    if len(data) < 8:
        last = data[-1] if data else Bar("", 0, 0, 0, 0)
        return TimeframeStructure(timeframe, "UNKNOWN", last.high, last.low, atr(data), 0.0)
    highs, lows = _swing_points(data)
    a = atr(data)
    direction = "RANGE"
    if len(highs) >= 2 and len(lows) >= 2:
        hh = highs[-1][1] > highs[-2][1]
        hl = lows[-1][1] > lows[-2][1]
        lh = highs[-1][1] < highs[-2][1]
        ll = lows[-1][1] < lows[-2][1]
        if hh and hl:
            direction = "UP"
        elif lh and ll:
            direction = "DOWN"
        elif hh != hl or lh != ll:
            direction = "TRANSITION"
    bodies = [b.body for b in data[-6:]]
    ranges = [b.range for b in data[-6:] if b.range > 0]
    body_ratio = (sum(bodies) / sum(ranges)) if ranges and sum(ranges) > 0 else 0.0
    displacement = abs(data[-1].close - data[-6].close)
    impulse = 0.0 if a <= 0 else displacement / (a * 5.0)
    impulse_score = min(2.0, 0.5 * body_ratio + impulse)
    last_high = highs[-1][1] if highs else max(b.high for b in data[-10:])
    last_low = lows[-1][1] if lows else min(b.low for b in data[-10:])
    return TimeframeStructure(timeframe, direction, last_high, last_low, a, impulse_score)


def classify_market(timeframes: dict[str, list[Bar]]) -> MarketStructureState:
    structures = {tf: classify_timeframe(tf, bars) for tf, bars in timeframes.items()}
    priority = [tf for tf in ("D1", "H4", "H1", "M30", "M15", "M5", "M1") if tf in structures]
    higher = [structures[tf] for tf in priority[:3]]
    up = sum(x.direction == "UP" for x in higher)
    down = sum(x.direction == "DOWN" for x in higher)
    transition = any(x.direction == "TRANSITION" for x in higher)
    reasons: list[str] = []
    if up >= 2:
        bias = Bias.LONG
        reasons.append("大周期结构多数为 HH/HL")
    elif down >= 2:
        bias = Bias.SHORT
        reasons.append("大周期结构多数为 LH/LL")
    else:
        bias = Bias.NEUTRAL
        reasons.append("大周期方向未形成多数")
    aligned = [x for x in structures.values() if x.direction in {"UP", "DOWN"}]
    impulse = mean([x.impulse_score for x in aligned]) if aligned else 0.0
    if transition:
        regime = MarketRegime.TRANSITION
        reasons.append("大周期出现结构转换")
    elif bias is Bias.NEUTRAL:
        regime = MarketRegime.RANGE
        reasons.append("方向性不足，按平衡/震荡处理")
    elif impulse >= 1.05 and len(aligned) >= 3:
        regime = MarketRegime.EXTREME_TREND
        reasons.append("多周期方向一致且位移/实体动能强")
    else:
        regime = MarketRegime.TREND
        reasons.append("存在明确趋势结构")
    state_id = ";".join(f"{tf}:{structures[tf].direction}" for tf in priority) + f"|{regime.value}|{bias.value}"
    return MarketStructureState(regime, bias, structures, state_id, tuple(reasons))
