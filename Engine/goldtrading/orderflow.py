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


class OrderFlowEngine:
    """Consumes ATAS events and converts them into a compact, explainable assessment."""

    def __init__(self, max_events: int = 5000) -> None:
        self.events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self.cvd = 0.0
        self.last_delta = 0.0

    def ingest(self, event: dict[str, Any]) -> None:
        self.events.append(event)
        payload = event.get("payload") or {}
        if event.get("type") in {"trade", "cumulative_trade"}:
            volume = float(payload.get("volume", 0.0) or 0.0)
            side = str(payload.get("aggressor_side", "")).upper()
            if side == "BUY":
                self.cvd += volume
            elif side == "SELL":
                self.cvd -= volume
        if "delta" in payload and payload.get("delta") is not None:
            self.last_delta = float(payload["delta"])

    def assess(self, lookback: int = 200) -> OrderFlowAssessment:
        recent = list(self.events)[-lookback:]
        score = 0.0
        evidence: list[str] = []
        buy_aggression = sell_aggression = 0.0
        for event in recent:
            t = str(event.get("type", "")).lower()
            p = event.get("payload") or {}
            strength = float(p.get("strength", event.get("strength", 1.0)) or 1.0)
            side = str(p.get("side", p.get("aggressor_side", ""))).upper()
            if t in {"trade", "cumulative_trade", "large_trade"}:
                volume = float(p.get("volume", 0.0) or 0.0)
                if side == "BUY": buy_aggression += volume
                if side == "SELL": sell_aggression += volume
            if t in {"absorption", "order_flow_signal"}:
                detail = str(p.get("event_type", p.get("detail", ""))).lower()
                if "buy" in detail or "lower" in detail or "sell_absorption" in detail:
                    score += strength
                    evidence.append("下方吸收/卖盘推进受阻")
                if "sell" in detail or "upper" in detail or "buy_absorption" in detail:
                    score -= strength
                    evidence.append("上方吸收/买盘推进受阻")
            if t in {"sweep", "order_flow_signal"}:
                detail = str(p.get("event_type", p.get("detail", ""))).lower()
                if "up" in detail or side == "BUY":
                    score += 0.6 * strength
                    evidence.append("向上主动扫单")
                elif "down" in detail or side == "SELL":
                    score -= 0.6 * strength
                    evidence.append("向下主动扫单")
            if t in {"exhaustion", "order_flow_signal"}:
                detail = str(p.get("event_type", p.get("detail", ""))).lower()
                if "seller" in detail or "sell" in detail:
                    score += 0.8 * strength
                    evidence.append("卖方衰竭")
                elif "buyer" in detail or "buy" in detail:
                    score -= 0.8 * strength
                    evidence.append("买方衰竭")
        total = buy_aggression + sell_aggression
        if total > 0:
            imbalance = (buy_aggression - sell_aggression) / total
            score += imbalance * 2.0
            if imbalance > 0.15: evidence.append("主动买盘占优")
            if imbalance < -0.15: evidence.append("主动卖盘占优")
        if score >= 1.5:
            label = "买方明显增强"
        elif score >= 0.45:
            label = "买方增强"
        elif score <= -1.5:
            label = "卖方明显增强"
        elif score <= -0.45:
            label = "卖方增强"
        elif evidence:
            label = "多空冲突"
        else:
            label = "中性" if recent else "数据不足"
        return OrderFlowAssessment(label, score, tuple(dict.fromkeys(evidence)), {"cvd": self.cvd, "delta": self.last_delta, "events": len(recent)})
