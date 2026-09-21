from Engine.goldtrading.degradation import classify_degradation


def test_full_stack_level_zero():
    x=classify_degradation(mt5_alive=True,atas_health='HEALTHY',ai_health='HEALTHY')
    assert x.level == 0 and x.allow_new_ai_trades


def test_ai_offline_level_two():
    x=classify_degradation(mt5_alive=True,atas_health='HEALTHY',ai_health='OFFLINE')
    assert x.level == 2 and not x.allow_new_ai_trades and x.protect_existing_positions


def test_all_enhancements_offline_level_four():
    x=classify_degradation(mt5_alive=True,atas_health='OFFLINE',ai_health='OFFLINE')
    assert x.level == 4 and x.allow_local_structure_analysis


def test_python_down_guardian_only():
    x=classify_degradation(python_alive=False,mt5_alive=True,atas_health='OFFLINE',ai_health='OFFLINE')
    assert x.level == 5 and x.protect_existing_positions
