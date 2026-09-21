from Engine.goldtrading.breakout import assess_breakout, BreakoutVerdict
from Engine.goldtrading.structure import Bar
from Engine.goldtrading.zones import PriceZone
from Engine.goldtrading.potential_zones import rank_potential_zones, ZoneStatus


def bar(o,h,l,c): return Bar('',o,h,l,c,100)


def test_false_breakout_closes_back_inside_resistance():
    z=PriceZone('RESISTANCE',100,101,3,2,'H1')
    bars=[bar(98,99,97,98.5),bar(99,100.5,98.5,100),bar(100,102,99.5,100.5)]
    x=assess_breakout(bars,[z])
    assert x.verdict == BreakoutVerdict.FALSE


def test_pending_entity_breakout():
    z=PriceZone('RESISTANCE',100,101,3,2,'H1')
    bars=[bar(98,99,97,98.5),bar(99,100.5,98.5,100.5),bar(100.5,103,100.4,102.5)]
    x=assess_breakout(bars,[z])
    assert x.verdict == BreakoutVerdict.PENDING


def test_potential_zone_marks_nearby_support():
    z=PriceZone('SUPPORT',99,100,3,2,'H1')
    p=rank_potential_zones(100.4,[z],1.0)
    assert p and p[0].status == ZoneStatus.APPROACHING
