from types import SimpleNamespace
from Engine.goldtrading.recovery import slot_from_guardian_state


def test_slot_from_guardian_state_defaults_and_values():
    s=SimpleNamespace(slot_a_active=True,slot_a_side='BUY',slot_a_lot=0.02,slot_a_entry_price=2500,
                      slot_a_sl=2490,slot_a_tp=2520,slot_a_entry_time=123,slot_a_mfe=8,slot_a_mae=3)
    x=slot_from_guardian_state(s,'A')
    assert x.active and x.side=='BUY' and x.lot==0.02 and x.mfe==8
    y=slot_from_guardian_state(SimpleNamespace(),'B')
    assert not y.active and y.lot==0
