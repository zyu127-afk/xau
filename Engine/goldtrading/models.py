from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class Health(str, Enum):
    HEALTHY = "HEALTHY"
    WARMING_UP = "WARMING_UP"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


class AiHealth(str, Enum):
    HEALTHY = "HEALTHY"
    SLOW = "SLOW"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    SERVER_ERROR = "SERVER_ERROR"
    OFFLINE = "OFFLINE"


class MarketRegime(str, Enum):
    EXTREME_TREND = "EXTREME_TREND"
    TREND = "TREND"
    RANGE = "RANGE"
    TRANSITION = "TRANSITION"


class Bias(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


@dataclass(slots=True)
class Snapshot:
    snapshot_id: str
    snapshot_time: datetime
    price_at_request: float
    gc_price: Optional[float]
    mt5_price: float
    market_state_id: str
    positions_fingerprint: str
    orderflow_state: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def now(
        cls,
        snapshot_id: str,
        mt5_price: float,
        gc_price: Optional[float],
        market_state_id: str,
        positions_fingerprint: str,
        orderflow_state: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> "Snapshot":
        return cls(
            snapshot_id=snapshot_id,
            snapshot_time=datetime.now(timezone.utc),
            price_at_request=mt5_price,
            gc_price=gc_price,
            mt5_price=mt5_price,
            market_state_id=market_state_id,
            positions_fingerprint=positions_fingerprint,
            orderflow_state=orderflow_state,
            payload=payload or {},
        )


@dataclass(slots=True)
class TradeIntent:
    intent_id: str
    action: str
    side: str
    lot: float
    snapshot_id: str
    reason: str
    valid_until: datetime
    zone_low: float
    zone_high: float
    stop_loss: float
    take_profit: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PositionState:
    position_id: str
    entry_id: str
    side: str
    lot: float
    entry_time: datetime
    entry_price: float
    original_sl: float
    current_sl: float
    current_tp: Optional[float]
    mfe: float = 0.0
    mae: float = 0.0
    current_pnl: float = 0.0
    entry_reason: str = ""
    market_regime: str = ""
    orderflow_state: str = ""
    ai_snapshot: str = ""
    exit_reason: str = ""
