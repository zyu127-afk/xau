from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Engine.goldtrading.orderflow import OrderFlowEngine
from Engine.goldtrading.price_alignment import PriceAlignmentEngine
from Engine.goldtrading.structure import Bar, classify_market
from Engine.goldtrading.zones import build_zones


def main():
    mapping = PriceAlignmentEngine(min_samples=30)
    for i in range(60):
        mapping.add(2600 + i * 0.1, 2590 + i * 0.1002)
    estimate = mapping.estimate()
    assert estimate is not None

    bars = []
    p = 2500.0
    for i in range(80):
        d = 2 if (i // 8) % 2 == 0 else -0.7
        o = p
        c = p + d
        bars.append(Bar(str(i), o, max(o, c) + 1, min(o, c) - 1, c, 100 + i))
        p = c

    state = classify_market({tf: bars for tf in ("D1", "H4", "H1", "M30", "M15", "M5", "M1")})
    flow = OrderFlowEngine()
    for _ in range(20):
        flow.ingest({"type": "trade", "payload": {"volume": 5, "aggressor_side": "BUY"}})
    zones = build_zones("H1", bars)

    print("mapping", estimate)
    print("state", state.regime.value, state.bias.value, state.state_id)
    print("orderflow", flow.assess())
    print("zones", zones[:6])
    print("SMOKE TEST OK")


if __name__ == "__main__":
    main()
