from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from .zones import PriceZone


class ZoneStatus(str, Enum):
    UNREACHED = "未到达"
    APPROACHING = "接近"
    ENTERED = "已进入"
    WAITING = "等待确认"
    TRIGGERED = "已触发"
    INVALID = "已失效"


@dataclass(frozen=True, slots=True)
class PotentialZone:
    side: str
    zone: PriceZone
    status: ZoneStatus
    distance: float
    score: float


def rank_potential_zones(price: float, zones: list[PriceZone], atr_value: float, limit: int = 3) -> list[PotentialZone]:
    out: list[PotentialZone] = []
    approach = max(atr_value * 0.50, 1e-9)
    for z in zones:
        side = "BUY" if z.kind == "SUPPORT" else "SELL"
        if z.low <= price <= z.high:
            status = ZoneStatus.ENTERED
            distance = 0.0
        elif price < z.low:
            distance = z.low - price
            # A support completely above current price has been broken and is not a valid buy support now.
            status = ZoneStatus.INVALID if z.kind == "SUPPORT" else (ZoneStatus.APPROACHING if distance <= approach else ZoneStatus.UNREACHED)
        else:
            distance = price - z.high
            # A resistance completely below current price has been broken and is not a valid sell resistance now.
            status = ZoneStatus.INVALID if z.kind == "RESISTANCE" else (ZoneStatus.APPROACHING if distance <= approach else ZoneStatus.UNREACHED)
        score = z.strength - distance / max(atr_value, 1e-9) * 0.10
        out.append(PotentialZone(side, z, status, distance, score))
    valid = [x for x in out if x.status is not ZoneStatus.INVALID]
    return sorted(valid, key=lambda x: (x.distance, -x.score))[:limit]


def with_confirmation(zone: PotentialZone, confirmed: bool, triggered: bool = False) -> PotentialZone:
    if triggered:
        status = ZoneStatus.TRIGGERED
    elif zone.status is ZoneStatus.ENTERED:
        status = ZoneStatus.WAITING if not confirmed else ZoneStatus.TRIGGERED
    else:
        status = zone.status
    return PotentialZone(zone.side, zone.zone, status, zone.distance, zone.score)
