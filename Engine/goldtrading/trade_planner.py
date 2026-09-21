from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from .models import Bias, MarketRegime
from .structure import MarketStructureState
from .zones import PriceZone, nearest_space
from .orderflow import OrderFlowAssessment


@dataclass(frozen=True, slots=True)
class TradePlan:
    side: str
    status: str
    zone: PriceZone | None
    triggers: tuple[str, ...]
    invalidation: tuple[str, ...]
    target_region: PriceZone | None
    reasons: tuple[str, ...]


def build_plans(price: float, structure: MarketStructureState, zones: Iterable[PriceZone], orderflow: OrderFlowAssessment) -> tuple[TradePlan, TradePlan]:
    zs = list(zones)
    supports = sorted([z for z in zs if z.kind == "SUPPORT"], key=lambda z: abs(z.mid - price))
    resistances = sorted([z for z in zs if z.kind == "RESISTANCE"], key=lambda z: abs(z.mid - price))
    long_zone = supports[0] if supports else None
    short_zone = resistances[0] if resistances else None
    long_target = next((z for z in resistances if z.low > price), None)
    short_target = next((z for z in supports if z.high < price), None)
    long_reasons: list[str] = []
    short_reasons: list[str] = []
    if structure.bias is Bias.LONG: long_reasons.append("大周期优先方向偏多")
    if structure.bias is Bias.SHORT: short_reasons.append("大周期优先方向偏空")
    if orderflow.score > 0.45: long_reasons.append(orderflow.label)
    if orderflow.score < -0.45: short_reasons.append(orderflow.label)
    if structure.regime is MarketRegime.RANGE:
        long_reasons.append("震荡：仅在下沿区域等待反向确认")
        short_reasons.append("震荡：仅在上沿区域等待反向确认")
    if structure.regime is MarketRegime.TRANSITION:
        long_reasons.append("转换状态：需要更强确认")
        short_reasons.append("转换状态：需要更强确认")
    long_status = "WAIT" if long_zone else "NO_ZONE"
    short_status = "WAIT" if short_zone else "NO_ZONE"
    long_triggers = ("价格进入做多区域", "M5/M1执行结构确认", "ATAS卖方衰竭/吸收或买方重新增强", "信号仍在有效期")
    short_triggers = ("价格进入做空区域", "M5/M1执行结构确认", "ATAS买方衰竭/吸收或卖方重新增强", "信号仍在有效期")
    long_invalid = ("大周期多头结构失效", "做多区域失效", "订单流持续反向", "有效利润空间消失")
    short_invalid = ("大周期空头结构失效", "做空区域失效", "订单流持续反向", "有效利润空间消失")
    return (
        TradePlan("BUY", long_status, long_zone, long_triggers, long_invalid, long_target, tuple(long_reasons)),
        TradePlan("SELL", short_status, short_zone, short_triggers, short_invalid, short_target, tuple(short_reasons)),
    )


def actual_space_is_worthwhile(price: float, side: str, zones: Iterable[PriceZone], spread_price: float, estimated_sl_distance: float) -> tuple[bool, str]:
    space = nearest_space(price, side, zones)
    if space is None:
        return True, "前方未识别到阻挡区域，由动态管理继续评估"
    real_cost = max(0.0, spread_price) + max(0.0, estimated_sl_distance)
    if space <= real_cost:
        return False, f"前方空间 {space:.3f} 无法覆盖真实成本/结构风险 {real_cost:.3f}"
    return True, f"前方可用空间 {space:.3f} 大于估算成本/风险 {real_cost:.3f}"
