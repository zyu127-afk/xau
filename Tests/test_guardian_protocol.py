from datetime import datetime, timezone, timedelta

from Engine.goldtrading.guardian_protocol import GuardianCommand
from Engine.goldtrading.guardian_server import GuardianServer


def test_wire_is_sanitized_and_timestamped():
    c = GuardianCommand(
        "id1", "OPEN", "A", "BUY", 0.01, 2490.0, None, 2498.0, 2502.0,
        datetime.now(timezone.utc) + timedelta(seconds=10), "reason|with\nnewline",
    )
    wire = c.to_wire()
    assert wire.startswith("GTS1|id1|OPEN|A|BUY|")
    assert "reason/with newline" in wire
    assert wire.endswith("\n")
    assert len(wire.rstrip("\n").split("|")) == 12


def test_wire_uses_empty_tp_when_take_profit_is_none():
    c = GuardianCommand(
        "id2", "OPEN", "B", "SELL", 0.02, 2510.0, None, 2500.0, 2505.0,
        datetime.now(timezone.utc) + timedelta(seconds=30), "test",
    )
    parts = c.to_wire().rstrip("\n").split("|")
    assert parts[0:5] == ["GTS1", "id2", "OPEN", "B", "SELL"]
    assert parts[7] == ""


def test_current_guardian_heartbeat_slot_shape_parses_all_fields():
    server = GuardianServer()
    slot_a = ["1", "BUY", "0.10", "2500.5", "2490.0", "2495.0", "2525.0", "1700000000", "12.5", "3.25"]
    slot_b = ["1", "SELL", "0.20", "2510.0", "2520.0", "2518.0", "2480.0", "1700000100", "9.0", "2.0"]
    parts = ["HB", "1700000200", "2504", "2505", "10", "2", "0", "0", *slot_a, *slot_b]
    assert len(parts) == 28

    server._parse_slot_v20(parts, 8, "slot_a_")
    server._parse_slot_v20(parts, 18, "slot_b_")

    assert server.state.slot_a_active is True
    assert server.state.slot_a_side == "BUY"
    assert server.state.slot_a_original_sl == 2490.0
    assert server.state.slot_a_sl == 2495.0
    assert server.state.slot_a_mfe == 12.5
    assert server.state.slot_b_active is True
    assert server.state.slot_b_side == "SELL"
    assert server.state.slot_b_original_sl == 2520.0
    assert server.state.slot_b_sl == 2518.0
    assert server.state.slot_b_mae == 2.0
