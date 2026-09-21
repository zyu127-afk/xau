from datetime import datetime, timedelta, timezone
from Engine.goldtrading.models import Snapshot, TradeIntent
from Engine.goldtrading.stale import validate_intent


def snap(snapshot_id="s1", price=2500.0, state="bull", positions="A:EMPTY|B:EMPTY", flow="buy"):
    return Snapshot(snapshot_id, datetime.now(timezone.utc), price, 2501.0, price, state, positions, flow)


def intent(snapshot_id="s1", zone_low=2495.0, zone_high=2505.0):
    return TradeIntent("i1", "OPEN", "BUY", 0.01, snapshot_id, "test", datetime.now(timezone.utc)+timedelta(seconds=10), zone_low, zone_high, 2490.0)


def test_valid_intent_passes():
    requested = snap()
    current = snap()
    ok, reason = validate_intent(intent(), requested, current, 10.0)
    assert ok and reason == "VALID"


def test_new_snapshot_is_stale():
    requested = snap("s1")
    current = snap("s2")
    ok, reason = validate_intent(intent("s1"), requested, current, 10.0)
    assert not ok and "newer snapshot" in reason


def test_position_change_is_stale():
    requested = snap(positions="A:EMPTY|B:EMPTY")
    current = snap(positions="A:e1:BUY:0.01:2490|B:EMPTY")
    ok, reason = validate_intent(intent(), requested, current, 10.0)
    assert not ok and "positions changed" in reason
