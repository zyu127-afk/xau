import pytest
from Engine.goldtrading.ai_client import OpenAICompatibleClient, REQUIRED_KEYS


def test_required_ai_keys_accept_complete_payload():
    payload={k: {} for k in REQUIRED_KEYS}
    payload['reasoning_summary']='ok'
    OpenAICompatibleClient.validate_payload(payload)


def test_required_ai_keys_reject_missing():
    with pytest.raises(ValueError):
        OpenAICompatibleClient.validate_payload({'market_regime':'TREND'})
