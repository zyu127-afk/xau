from __future__ import annotations

from pathlib import Path
import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TOKEN_FILE = PROJECT_ROOT / "Runtime" / "dashboard.token"


class DashboardClient:
    def __init__(self, url: str = "http://127.0.0.1:17840", token_file: Path | None = None) -> None:
        self.url = url.rstrip("/")
        self.state: dict = {}
        self.token_file = token_file or DEFAULT_TOKEN_FILE

    def _merge(self, target: dict, source: dict) -> None:
        for key, value in source.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                self._merge(target[key], value)
            else:
                target[key] = value

    def _token(self) -> str:
        try:
            return self.token_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    async def push(self, payload: dict) -> bool:
        self._merge(self.state, payload)
        token = self._token()
        if not token:
            return False
        try:
            async with httpx.AsyncClient(timeout=0.5) as client:
                r = await client.put(
                    f"{self.url}/api/state",
                    json=payload,
                    headers={"X-GTS-Token": token},
                )
                return r.is_success
        except httpx.HTTPError:
            return False
