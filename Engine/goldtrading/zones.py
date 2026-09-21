from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from .structure import Bar, atr


@dataclass(frozen=True, slots=True)
class PriceZone:
    kind: str
    low: float
    high: float
    strength: float
    touches: int
    source: str

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2.0


def _pivots(bars: list[Bar], wing: int = 2) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for i in range(wing, len(bars) - wing):
        if all(bars[i].high >= bars[j].high for j in range(i - wing, i + wing + 1) if j != i):
            out.append(("RESISTANCE", bars[i].high))
        if all(bars[i].low <= bars[j].low for j in range(i - wing, i + wing + 1) if j != i):
            out.append(("SUPPORT", bars[i].low))
    return out


def build_zones(timeframe: str, bars: Iterable[Bar], max_each: int = 3) -> list[PriceZone]:
    data = list(bars)
    if len(data) < 10:
        return []
    width = max(atr(data) * 0.18, 1e-9)
    pivots = _pivots(data)
    clusters: list[dict] = []
    for kind, price in pivots:
        found = None
        for c in clusters:
            if c["kind"] == kind and abs(c["center"] - price) <= width * 2.0:
                found = c
                break
        if found is None:
            clusters.append({"kind": kind, "prices": [price], "center": price})
        else:
            found["prices"].append(price)
            found["center"] = sum(found["prices"]) / len(found["prices"])
    zones: list[PriceZone] = []
    for c in clusters:
        prices = c["prices"]
        center = c["center"]
        touches = len(prices)
        recency_bonus = 0.0
        for idx, (_, p) in enumerate(reversed(pivots[-20:])):
            if abs(p - center) <= width * 2.0:
                recency_bonus = max(recency_bonus, max(0.0, 1.0 - idx / 20.0))
        strength = touches + recency_bonus
        zones.append(PriceZone(c["kind"], min(prices) - width, max(prices) + width, strength, touches, timeframe))
    supports = sorted((z for z in zones if z.kind == "SUPPORT"), key=lambda z: z.strength, reverse=True)[:max_each]
    resistances = sorted((z for z in zones if z.kind == "RESISTANCE"), key=lambda z: z.strength, reverse=True)[:max_each]
    return supports + resistances


def nearest_space(price: float, side: str, zones: Iterable[PriceZone]) -> float | None:
    if side.upper() == "BUY":
        ahead = [z.low - price for z in zones if z.kind == "RESISTANCE" and z.low > price]
    else:
        ahead = [price - z.high for z in zones if z.kind == "SUPPORT" and z.high < price]
    return min(ahead) if ahead else None
