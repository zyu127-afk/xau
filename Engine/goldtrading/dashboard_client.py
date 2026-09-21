from __future__ import annotations

import httpx


class DashboardClient:
    def __init__(self, url: str = "http://127.0.0.1:17840") -> None:
        self.url = url.rstrip("/")

    async def push(self, payload: dict) -> bool:
        try:
            async with httpx.AsyncClient(timeout=0.5) as client:
                r = await client.put(f"{self.url}/api/state", json=payload)
                return r.is_success
        except httpx.HTTPError:
            return False
