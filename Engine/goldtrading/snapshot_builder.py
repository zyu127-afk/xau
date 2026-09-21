from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from .models import Snapshot


def fingerprint_positions(positions: list[dict]) -> str:
    material = []
    for p in sorted(positions, key=lambda x: str(x.get("ticket", ""))):
        material.append({
            "ticket": p.get("ticket"), "type": p.get("type"), "volume": p.get("volume"),
            "price_open": p.get("price_open"), "sl": p.get("sl"), "tp": p.get("tp"),
            "magic": p.get("magic"), "comment": p.get("comment"),
        })
    raw = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:24]


def build_snapshot(mt5_price: float, gc_price: float | None, market_state_id: str,
                   positions: list[dict], orderflow_state: str, payload: dict) -> Snapshot:
    return Snapshot(
        snapshot_id=uuid.uuid4().hex,
        snapshot_time=datetime.now(timezone.utc),
        price_at_request=mt5_price,
        gc_price=gc_price,
        mt5_price=mt5_price,
        market_state_id=market_state_id,
        positions_fingerprint=fingerprint_positions(positions),
        orderflow_state=orderflow_state,
        payload=payload,
    )
