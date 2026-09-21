from Engine.goldtrading.event_outcomes import FastEventOutcomeTracker
from Engine.goldtrading.orderflow import OrderFlowEngine


def event(kind='sweep'):
    return {
        'type': kind,
        'ts_utc': '2026-09-21T10:00:00+00:00',
        'instrument': 'GCZ6',
        'mbo_available': False,
        'payload': {'price': 2600.0, 'strength': 2.0, 'side': 'BUY', 'secret_field': 'drop-me'},
    }


def test_fast_event_outcomes_use_configured_horizons():
    t=FastEventOutcomeTracker(horizons=(5,30))
    uid=t.add(event(), 2500.0)
    assert uid
    created=t.pending[0].created_monotonic
    assert t.evaluate(2501.0, created+4.9)==[]
    first=t.evaluate(2502.0, created+5.0)
    assert len(first)==1 and first[0].horizon_seconds==5 and first[0].move==2.0
    second=t.evaluate(2498.0, created+30.0)
    assert len(second)==1 and second[0].horizon_seconds==30 and second[0].move==-2.0
    assert not t.pending


def test_orderflow_important_events_are_compact_and_do_not_invent_mbo_fields():
    e=OrderFlowEngine(); e.ingest(event())
    rows=e.important_events(5)
    assert len(rows)==1
    assert rows[0]['mbo_available'] is False
    assert 'secret_field' not in rows[0]['payload']
    assert 'order_count' not in rows[0]['payload']
