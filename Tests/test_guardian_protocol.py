from datetime import datetime, timezone, timedelta
from Engine.goldtrading.guardian_protocol import GuardianCommand


def test_wire_is_sanitized_and_timestamped():
    c=GuardianCommand("id1","OPEN","A","BUY",0.01,2490.0,None,2498.0,2502.0,
                      datetime.now(timezone.utc)+timedelta(seconds=10),"reason|with\nnewline")
    wire=c.to_wire()
    assert wire.startswith("GTS1|id1|OPEN|A|BUY|")
    assert "reason/with newline" in wire
    assert wire.endswith("\n")
