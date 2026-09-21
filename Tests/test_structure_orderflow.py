from Engine.goldtrading.structure import Bar, classify_market
from Engine.goldtrading.orderflow import OrderFlowEngine
from Engine.goldtrading.models import Bias


def up_bars(n=40, start=2400.0):
    bars=[]
    p=start
    for i in range(n):
        o=p; c=p+2.0; bars.append(Bar(str(i),o,c+1,o-0.5,c,100)); p=c
    return bars


def test_structure_produces_state_id():
    bars=up_bars()
    state=classify_market({"D1":bars,"H4":bars,"H1":bars,"M15":bars,"M5":bars})
    assert state.state_id
    assert state.bias in {Bias.LONG, Bias.NEUTRAL}


def test_orderflow_buying_assessment():
    engine=OrderFlowEngine()
    for _ in range(10):
        engine.ingest({"type":"trade","payload":{"volume":10,"aggressor_side":"BUY"}})
    for _ in range(2):
        engine.ingest({"type":"trade","payload":{"volume":1,"aggressor_side":"SELL"}})
    a=engine.assess()
    assert a.score > 0
    assert "买方" in a.label
