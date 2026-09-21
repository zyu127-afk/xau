from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from Engine.goldtrading.config import ConfigValidationError, validate_raw_config


def example_config():
    return yaml.safe_load(Path("Config/config.example.yaml").read_text(encoding="utf-8"))


def test_example_config_passes_v1_safety_validation():
    data = example_config()
    validate_raw_config(data)
    assert data["system"]["max_position_logics"] == 2
    assert data["trading"]["weekend_protection"] is True
    assert data["trading"]["require_server_sl"] is True
    assert data["history"]["rolling_days"] >= 90
    assert data["atas"]["require_mbo"] is False


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda x: x["system"].__setitem__("max_position_logics", 3), "max_position_logics"),
        (lambda x: x["trading"].__setitem__("weekend_protection", False), "weekend_protection"),
        (lambda x: x["trading"].__setitem__("require_server_sl", False), "require_server_sl"),
        (lambda x: x["trading"].__setitem__("default_lot", 0), "default_lot"),
        (lambda x: x["engine"].__setitem__("host", "0.0.0.0"), "loopback"),
        (lambda x: x["ui"].__setitem__("port", 70000), "ui.port"),
        (lambda x: x["price_mapping"].__setitem__("min_samples", 500), "rolling_window"),
        (lambda x: x["price_mapping"].__setitem__("min_correlation", 1.5), "min_correlation"),
        (lambda x: x["ai"].__setitem__("min_confidence", 1.1), "min_confidence"),
        (lambda x: x["history"].__setitem__("rolling_days", 30), "rolling_days"),
        (lambda x: x["history"].__setitem__("no_trade_dedupe_seconds", -1), "no_trade_dedupe_seconds"),
        (lambda x: x["atas"].__setitem__("require_mbo", "false"), "require_mbo"),
    ],
)
def test_invalid_v1_safety_config_is_rejected(mutator, match):
    data = deepcopy(example_config())
    mutator(data)
    with pytest.raises(ConfigValidationError, match=match):
        validate_raw_config(data)
