from __future__ import annotations

from dataclasses import dataclass, asdict
import time
from typing import Any
from uuid import uuid4


FAST_EVENT_TYPES = {
    "large_trade", "cancel", "dom_change", "dom_fast_change", "delta_spike",
    "sweep", "iceberg", "absorption", "footprint_anomaly", "exhaustion",
    "liquidity_pull", "liquidity_stack", "order_flow_signal",
}


@dataclass(slots=True)
class PendingFastEvent:
    event_uid: str
    created_monotonic: float
    ts_utc: str
    event_type: str
    instrument: str
    gc_price: float | None
    mt5_price: float | None
    strength: float | None
    payload: dict[str, Any]
    completed_horizons: set[int]


@dataclass(frozen=True, slots=True)
class EventOutcome:
    event_uid: str
    horizon_seconds: int
    ts_utc: str
    event_type: str
    instrument: str
    gc_price: float | None
    start_mt5: float | None
    end_mt5: float
    move: float | None
    strength: float | None


class FastEventOutcomeTracker:
    """Tracks what price did after important ATAS events without blocking the feed."""

    def __init__(self, horizons: tuple[int, ...] = (5, 30, 60), max_pending: int = 1000) -> None:
        self.horizons = tuple(sorted({int(x) for x in horizons if int(x) > 0}))
        self.max_pending = max(10, int(max_pending))
        self.pending: list[PendingFastEvent] = []
        self.recent_outcomes: list[dict[str, Any]] = []

    def reset(self) -> None:
        self.pending.clear()
        self.recent_outcomes.clear()

    @staticmethod
    def is_fast_event(event: dict[str, Any]) -> bool:
        return str(event.get("type", "")).lower() in FAST_EVENT_TYPES

    def add(self, event: dict[str, Any], mapped_mt5: float | None) -> str | None:
        if not self.is_fast_event(event):
            return None
        p = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        raw_gc = p.get("price", p.get("last"))
        try: gc_price = None if raw_gc is None else float(raw_gc)
        except (TypeError, ValueError): gc_price = None
        raw_strength = p.get("strength", event.get("strength"))
        try: strength = None if raw_strength is None else float(raw_strength)
        except (TypeError, ValueError): strength = None
        item = PendingFastEvent(
            event_uid=uuid4().hex,
            created_monotonic=time.monotonic(),
            ts_utc=str(event.get("ts_utc") or ""),
            event_type=str(event.get("type") or "unknown"),
            instrument=str(event.get("instrument") or ""),
            gc_price=gc_price,
            mt5_price=None if mapped_mt5 is None else float(mapped_mt5),
            strength=strength,
            payload=dict(p),
            completed_horizons=set(),
        )
        self.pending.append(item)
        if len(self.pending) > self.max_pending:
            del self.pending[:len(self.pending) - self.max_pending]
        return item.event_uid

    def evaluate(self, current_mt5: float, now_monotonic: float | None = None) -> list[EventOutcome]:
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        outcomes: list[EventOutcome] = []
        keep: list[PendingFastEvent] = []
        for item in self.pending:
            age = now - item.created_monotonic
            for horizon in self.horizons:
                if horizon in item.completed_horizons or age < horizon:
                    continue
                move = None if item.mt5_price is None else float(current_mt5) - item.mt5_price
                outcome = EventOutcome(
                    item.event_uid, horizon, item.ts_utc, item.event_type, item.instrument,
                    item.gc_price, item.mt5_price, float(current_mt5), move, item.strength,
                )
                outcomes.append(outcome)
                self.recent_outcomes.append(asdict(outcome))
                item.completed_horizons.add(horizon)
            if len(item.completed_horizons) < len(self.horizons):
                keep.append(item)
        self.pending = keep
        if len(self.recent_outcomes) > 200:
            self.recent_outcomes = self.recent_outcomes[-200:]
        return outcomes

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.recent_outcomes[-max(1, int(limit)):]
