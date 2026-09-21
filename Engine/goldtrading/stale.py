from __future__ import annotations

from datetime import datetime, timezone
from .models import Snapshot, TradeIntent


def validate_intent(
    intent: TradeIntent,
    requested: Snapshot,
    current: Snapshot,
    max_price_move: float,
) -> tuple[bool, str]:
    """Reject AI output whenever the world no longer matches the request snapshot."""
    now = datetime.now(timezone.utc)
    if now > intent.valid_until:
        return False, "AI_SIGNAL_STALE: expired"
    if intent.snapshot_id != requested.snapshot_id:
        return False, "AI_SIGNAL_STALE: snapshot mismatch"
    if current.snapshot_id != requested.snapshot_id:
        return False, "AI_SIGNAL_STALE: newer snapshot exists"
    if current.market_state_id != requested.market_state_id:
        return False, "AI_SIGNAL_STALE: market state changed"
    if current.positions_fingerprint != requested.positions_fingerprint:
        return False, "AI_SIGNAL_STALE: positions changed"
    if current.orderflow_state != requested.orderflow_state:
        return False, "AI_SIGNAL_STALE: orderflow changed"
    if abs(current.mt5_price - requested.mt5_price) > max_price_move:
        return False, "AI_SIGNAL_STALE: price moved"
    if not (intent.zone_low <= current.mt5_price <= intent.zone_high):
        return False, "AI_SIGNAL_STALE: price outside valid zone"
    return True, "VALID"
