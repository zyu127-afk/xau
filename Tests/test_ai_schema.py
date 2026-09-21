import copy

import pytest

from Engine.goldtrading.ai_client import OpenAICompatibleClient


def valid_payload():
    return {
        "market_regime": "TREND",
        "bias": "LONG",
        "confidence": 0.72,
        "key_support": {"low": 2600.0, "high": 2602.0},
        "key_resistance": {"low": 2610.0, "high": 2612.0},
        "long_zones": [{"low": 2601.0, "high": 2603.0}],
        "short_zones": [{"low": 2610.0, "high": 2612.0}],
        "entry_plan_long": {
            "action": "OPEN",
            "zone_low": 2601.0,
            "zone_high": 2603.0,
            "stop_loss": 2598.5,
            "take_profit": 2610.0,
            "lot": 0.01,
            "valid_for_seconds": 20,
            "reason": "trend pullback confirmation",
            "confirmations": ["structure", "orderflow"],
        },
        "entry_plan_short": {
            "action": "WAIT",
            "zone_low": None,
            "zone_high": None,
            "stop_loss": None,
            "take_profit": None,
            "lot": None,
            "valid_for_seconds": 20,
            "reason": "wait for resistance confirmation",
            "confirmations": [],
        },
        "invalidation": {"long": "support failure", "short": "resistance failure"},
        "orderflow_assessment": "buyers strengthening",
        "position_management": {"A": "hold", "B": "none"},
        "no_trade_conditions": ["mapping stale", "orderflow conflict"],
        "validity": {"max_price_move": 1.5, "expires_in_seconds": 20},
        "reasoning_summary": "trend remains constructive; only long setup is executable",
    }


def test_strict_ai_schema_accepts_valid_payload():
    OpenAICompatibleClient.validate_payload(valid_payload())


def test_strict_ai_schema_rejects_missing_required_key():
    payload = valid_payload()
    payload.pop("validity")
    with pytest.raises(ValueError):
        OpenAICompatibleClient.validate_payload(payload)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda p: p.__setitem__("market_regime", "UNKNOWN"), "market_regime"),
        (lambda p: p.__setitem__("confidence", "0.8"), "confidence"),
        (lambda p: p.__setitem__("confidence", 1.1), "confidence"),
        (lambda p: p["entry_plan_long"].__setitem__("action", "BUY_NOW"), "action"),
        (lambda p: p["entry_plan_long"].__setitem__("valid_for_seconds", 0), "valid_for_seconds"),
        (lambda p: p["entry_plan_long"].__setitem__("stop_loss", -1.0), "executable prices"),
        (lambda p: p["entry_plan_long"].__setitem__("lot", 0.0), "lot"),
        (lambda p: p["validity"].__setitem__("max_price_move", 0.0), "max_price_move"),
        (lambda p: p["validity"].__setitem__("expires_in_seconds", 121), "expires_in_seconds"),
    ],
)
def test_strict_ai_schema_rejects_invalid_types_and_ranges(mutator, match):
    payload = copy.deepcopy(valid_payload())
    mutator(payload)
    with pytest.raises(ValueError, match=match):
        OpenAICompatibleClient.validate_payload(payload)
