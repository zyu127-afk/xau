from datetime import datetime, timezone
import pytest
from Engine.goldtrading.models import PositionState
from Engine.goldtrading.positions import PositionBook


def pos(side="BUY", sl=2490.0):
    return PositionState("p1", "e1", side, 0.01, datetime.now(timezone.utc), 2500.0, sl, sl, None)


def test_requires_server_sl():
    book = PositionBook()
    with pytest.raises(ValueError):
        book.open("A", pos(sl=0.0))


def test_tracks_mfe_mae():
    book = PositionBook()
    book.open("A", pos())
    book.update_market(2505.0, {"A": 5.0})
    book.update_market(2498.0, {"A": -2.0})
    state = book.slots["A"]
    assert state is not None
    assert state.mfe == 5.0
    assert state.mae == 2.0


def test_only_two_slots_exist():
    book = PositionBook()
    book.open("A", pos())
    p2 = pos(); p2.entry_id="e2"; p2.position_id="p2"
    book.open("B", p2)
    assert book.occupied() == 2
    with pytest.raises(KeyError):
        book.open("C", pos())
