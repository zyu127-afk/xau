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
    def validate_payload(payload: dict[str, Any]) -> None:
        missing = sorted(REQUIRED_KEYS.difference(payload))
        if missing:
            raise ValueError(f"AI JSON missing keys: {', '.join(missing)}")

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
                            await asyncio.sleep(0.5 * (attempt + 1))
                            continue
                        status = "RATE_LIMIT"
                        break
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    payload = json.loads(content)
                    self.validate_payload(payload)
                    latency = (time.perf_counter() - started) * 1000
                    return AiResult("HEALTHY" if latency <= self.timeout * 700 else "SLOW", latency, payload)
                except httpx.TimeoutException as exc:
                    last_error = str(exc)
                    status = "TIMEOUT"
                except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
                    last_error = str(exc)
                    status = "SERVER_ERROR"
                if attempt < self.retry:
                    await asyncio.sleep(0.5 * (attempt + 1))
        return AiResult(status, (time.perf_counter() - started) * 1000, None, last_error)
