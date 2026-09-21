from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
import httpx


REQUIRED_KEYS = {
    "market_regime", "bias", "confidence", "key_support", "key_resistance",
    "long_zones", "short_zones", "entry_plan_long", "entry_plan_short",
    "invalidation", "orderflow_assessment", "position_management",
    "no_trade_conditions", "validity", "reasoning_summary",
}
VALID_REGIMES = {"EXTREME_TREND", "TREND", "RANGE", "TRANSITION"}
VALID_BIASES = {"LONG", "SHORT", "NEUTRAL"}
VALID_ACTIONS = {"OPEN", "WAIT", "NO_TRADE"}


@dataclass(frozen=True, slots=True)
class AiResult:
    status: str
    latency_ms: float
    payload: dict[str, Any] | None
    error: str = ""


class OpenAICompatibleClient:
    def __init__(self, cfg: dict[str, Any], api_key: str) -> None:
        self.base_url = str(cfg.get("base_url", "")).rstrip("/")
        self.model = str(cfg.get("model", ""))
        self.timeout = float(cfg.get("timeout_seconds", 15))
        self.retry = int(cfg.get("retry", 1))
        self.max_tokens = int(cfg.get("max_tokens", 2000))
        self.temperature = float(cfg.get("temperature", 0.1))
        self.proxy = str(cfg.get("proxy", "")) or None
        self.api_key = api_key

    @staticmethod
    def _finite_number(value: Any, name: str, *, nullable: bool = False) -> float | None:
        if value is None and nullable:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"AI JSON {name} must be numeric")
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            raise ValueError(f"AI JSON {name} must be finite")
        return number

    @classmethod
    def _validate_plan(cls, plan: Any, name: str) -> None:
        if not isinstance(plan, dict):
            raise ValueError(f"AI JSON {name} must be an object")
        action = str(plan.get("action", "")).upper()
        if action not in VALID_ACTIONS:
            raise ValueError(f"AI JSON {name}.action invalid")
        valid_for = plan.get("valid_for_seconds")
        if isinstance(valid_for, bool) or not isinstance(valid_for, int) or not 1 <= valid_for <= 120:
            raise ValueError(f"AI JSON {name}.valid_for_seconds must be integer 1..120")
        if action == "OPEN":
            lo = cls._finite_number(plan.get("zone_low"), f"{name}.zone_low")
            hi = cls._finite_number(plan.get("zone_high"), f"{name}.zone_high")
            sl = cls._finite_number(plan.get("stop_loss"), f"{name}.stop_loss")
            if lo is None or hi is None or sl is None or lo > hi or sl <= 0:
                raise ValueError(f"AI JSON {name} has invalid executable prices")
            cls._finite_number(plan.get("take_profit"), f"{name}.take_profit", nullable=True)
            lot = cls._finite_number(plan.get("lot"), f"{name}.lot", nullable=True)
            if lot is not None and lot <= 0:
                raise ValueError(f"AI JSON {name}.lot must be positive")
        else:
            for key in ("zone_low", "zone_high", "stop_loss", "take_profit", "lot"):
                if plan.get(key) is not None:
                    cls._finite_number(plan.get(key), f"{name}.{key}", nullable=True)
        if not isinstance(plan.get("confirmations", []), list):
            raise ValueError(f"AI JSON {name}.confirmations must be an array")

    @classmethod
    def validate_payload(cls, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise ValueError("AI JSON root must be an object")
        missing = sorted(REQUIRED_KEYS.difference(payload))
        if missing:
            raise ValueError(f"AI JSON missing keys: {', '.join(missing)}")
        if str(payload["market_regime"]).upper() not in VALID_REGIMES:
            raise ValueError("AI JSON market_regime invalid")
        if str(payload["bias"]).upper() not in VALID_BIASES:
            raise ValueError("AI JSON bias invalid")
        confidence = cls._finite_number(payload["confidence"], "confidence")
        if confidence is None or not 0.0 <= confidence <= 1.0:
            raise ValueError("AI JSON confidence must be 0..1")
        if not isinstance(payload["long_zones"], list) or not isinstance(payload["short_zones"], list):
            raise ValueError("AI JSON long_zones/short_zones must be arrays")
        if not isinstance(payload["no_trade_conditions"], list):
            raise ValueError("AI JSON no_trade_conditions must be an array")
        cls._validate_plan(payload["entry_plan_long"], "entry_plan_long")
        cls._validate_plan(payload["entry_plan_short"], "entry_plan_short")
        validity = payload["validity"]
        if not isinstance(validity, dict):
            raise ValueError("AI JSON validity must be an object")
        max_move = cls._finite_number(validity.get("max_price_move"), "validity.max_price_move")
        if max_move is None or max_move <= 0:
            raise ValueError("AI JSON validity.max_price_move must be positive")
        expires = validity.get("expires_in_seconds")
        if isinstance(expires, bool) or not isinstance(expires, int) or not 1 <= expires <= 120:
            raise ValueError("AI JSON validity.expires_in_seconds must be integer 1..120")
        if not isinstance(payload["reasoning_summary"], str):
            raise ValueError("AI JSON reasoning_summary must be a string")

    async def analyze(self, system_prompt: str, dynamic_payload: dict[str, Any]) -> AiResult:
        if not self.base_url or not self.model or not self.api_key:
            return AiResult("OFFLINE", 0.0, None, "AI configuration incomplete")
        import time
        started = time.perf_counter()
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(dynamic_payload, ensure_ascii=False, separators=(",", ":"))},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        last_error = ""
        status = "SERVER_ERROR"
        transport_args: dict[str, Any] = {}
        if self.proxy:
            transport_args["proxy"] = self.proxy
        async with httpx.AsyncClient(timeout=self.timeout, **transport_args) as client:
            for attempt in range(self.retry + 1):
                try:
                    response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
                    if response.status_code == 429:
                        last_error = "rate limited"
                        if attempt < self.retry:
                            await asyncio.sleep(0.5 * (attempt + 1)); continue
                        status = "RATE_LIMIT"; break
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    payload = json.loads(content)
                    self.validate_payload(payload)
                    latency = (time.perf_counter() - started) * 1000
                    return AiResult("HEALTHY" if latency <= self.timeout * 700 else "SLOW", latency, payload)
                except httpx.TimeoutException as exc:
                    last_error = str(exc); status = "TIMEOUT"
                except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    last_error = str(exc); status = "SERVER_ERROR"
                if attempt < self.retry:
                    await asyncio.sleep(0.5 * (attempt + 1))
        return AiResult(status, (time.perf_counter() - started) * 1000, None, last_error)
