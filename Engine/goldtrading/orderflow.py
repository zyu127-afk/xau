from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class OrderFlowAssessment:
    label: str
    score: float
    evidence: tuple[str, ...]
    raw: dict[str, Any]


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class OrderFlowEngine:
    """Consumes ATAS events and converts them into a compact, explainable assessment."""

    IMPORTANT_TYPES = {
        "large_trade", "cancel", "dom_change", "dom_fast_change", "delta_spike",
        "sweep", "iceberg", "absorption", "exhaustion", "liquidity_pull",
        "liquidity_stack", "footprint_anomaly", "imbalance", "order_flow_signal",
    }
    IMPORTANT_KEYS = (
        "price", "last", "volume", "side", "aggressor_side", "strength",
        "event_type", "detail", "delta", "delta_ratio", "imbalance",
        "bid_size", "ask_size", "order_count",
    )

    def __init__(self, max_events: int = 5000) -> None:
        self.events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self.cvd = 0.0
        self.last_delta = 0.0
        self.instrument = ""

    def reset(self) -> None:
        self.events.clear()
        self.cvd = 0.0
        self.last_delta = 0.0

    def ingest(self, event: dict[str, Any]) -> None:
        instrument = str(event.get("instrument") or "")
        if instrument and self.instrument and instrument != self.instrument:
            self.reset()
        if instrument:
            self.instrument = instrument
        self.events.append(event)
        payload = event.get("payload") or {}
        if event.get("type") in {"trade", "cumulative_trade", "large_trade"}:
            volume = _number(payload.get("volume"))
            side = str(payload.get("aggressor_side", payload.get("side", ""))).upper()
            if side == "BUY": self.cvd += volume
            elif side == "SELL": self.cvd -= volume
        if "delta" in payload and payload.get("delta") is not None:
            self.last_delta = _number(payload.get("delta"))

    def important_events(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return compact recent events; never invent MBO-only fields that were not supplied."""
        out: list[dict[str, Any]] = []
        for event in reversed(self.events):
            event_type = str(event.get("type", "")).lower()
            if event_type not in self.IMPORTANT_TYPES:
                continue
            p = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            compact = {k: p.get(k) for k in self.IMPORTANT_KEYS if k in p}
            out.append({
                "type": event.get("type"),
                "ts_utc": event.get("ts_utc"),
                "instrument": event.get("instrument"),
                "mbo_available": bool(event.get("mbo_available", False)),
                "payload": compact,
            })
            if len(out) >= max(1, int(limit)):
                break
        out.reverse()
        return out

    def assess(self, lookback: int = 200) -> OrderFlowAssessment:
        recent = list(self.events)[-lookback:]
        score = 0.0
        evidence: list[str] = []
        buy_aggression = sell_aggression = 0.0
        dom_bid = dom_ask = 0.0
        for event in recent:
            t = str(event.get("type", "")).lower()
            p = event.get("payload") or {}
            strength = max(0.0, min(5.0, _number(p.get("strength", event.get("strength", 1.0)), 1.0)))
            side = str(p.get("side", p.get("aggressor_side", ""))).upper()
            if t in {"trade", "cumulative_trade", "large_trade"}:
                volume = _number(p.get("volume"))
                if side == "BUY": buy_aggression += volume
                if side == "SELL": sell_aggression += volume
                if t == "large_trade" and volume > 0:
                    evidence.append("大单主动买入" if side == "BUY" else "大单主动卖出" if side == "SELL" else "检测到大单")
            if t in {"dom", "depth", "book"}:
                dom_bid += _number(p.get("bid_size")); dom_ask += _number(p.get("ask_size"))
            if t in {"absorption", "order_flow_signal"}:
                detail = str(p.get("event_type", p.get("detail", ""))).lower()
                if "sell_absorption" in detail or "lower" in detail or "bid_absorption" in detail:
                    score += strength; evidence.append("下方吸收/卖盘推进受阻")
                if "buy_absorption" in detail or "upper" in detail or "ask_absorption" in detail:
                    score -= strength; evidence.append("上方吸收/买盘推进受阻")
            if t in {"sweep", "order_flow_signal"}:
                detail = str(p.get("event_type", p.get("detail", ""))).lower()
                if "up" in detail or side == "BUY": score += 0.6 * strength; evidence.append("向上主动扫单")
                elif "down" in detail or side == "SELL": score -= 0.6 * strength; evidence.append("向下主动扫单")
            if t in {"exhaustion", "order_flow_signal"}:
                detail = str(p.get("event_type", p.get("detail", ""))).lower()
                if "seller" in detail or "sell" in detail: score += 0.8 * strength; evidence.append("卖方衰竭")
                elif "buyer" in detail or "buy" in detail: score -= 0.8 * strength; evidence.append("买方衰竭")
            if t in {"liquidity_stack", "liquidity_pull", "order_flow_signal"}:
                detail = str(p.get("event_type", p.get("detail", ""))).lower()
                if "bid_stack" in detail or "ask_pull" in detail: score += 0.45 * strength; evidence.append("买侧流动性增强")
                elif "ask_stack" in detail or "bid_pull" in detail: score -= 0.45 * strength; evidence.append("卖侧流动性增强")
            if t in {"imbalance", "footprint", "order_flow_signal"}:
                imbalance = _number(p.get("imbalance", p.get("delta_ratio", 0.0)))
                if imbalance > 0.15: score += min(1.0, imbalance) * 0.7; evidence.append("Footprint买方不平衡")
                elif imbalance < -0.15: score += max(-1.0, imbalance) * 0.7; evidence.append("Footprint卖方不平衡")
            if t in {"iceberg", "order_flow_signal"}:
                detail = str(p.get("event_type", p.get("detail", ""))).lower()
                if "bid" in detail or "buy" in detail: score += 0.5 * strength; evidence.append("买侧疑似冰山")
                elif "ask" in detail or "sell" in detail: score -= 0.5 * strength; evidence.append("卖侧疑似冰山")
        total = buy_aggression + sell_aggression
        if total > 0:
            imbalance = (buy_aggression - sell_aggression) / total
            score += imbalance * 2.0
            if imbalance > 0.15: evidence.append("主动买盘占优")
            if imbalance < -0.15: evidence.append("主动卖盘占优")
        dom_total = dom_bid + dom_ask
        if dom_total > 0:
            dom_imbalance = (dom_bid - dom_ask) / dom_total
            score += dom_imbalance * 0.5
            if dom_imbalance > 0.2: evidence.append("DOM买侧挂单占优")
            if dom_imbalance < -0.2: evidence.append("DOM卖侧挂单占优")
        if score >= 1.5: label = "买方明显增强"
        elif score >= 0.45: label = "买方增强"
        elif score <= -1.5: label = "卖方明显增强"
        elif score <= -0.45: label = "卖方增强"
        elif evidence: label = "多空冲突"
        else: label = "中性" if recent else "数据不足"
        return OrderFlowAssessment(label, score, tuple(dict.fromkeys(evidence)), {
            "cvd": self.cvd, "delta": self.last_delta, "events": len(recent), "instrument": self.instrument,
            "buy_aggression": buy_aggression, "sell_aggression": sell_aggression,
            "dom_bid": dom_bid, "dom_ask": dom_ask,
        })
