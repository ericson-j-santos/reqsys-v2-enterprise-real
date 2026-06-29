from __future__ import annotations

from typing import Any

import httpx


class HttpxGateway:
    def __init__(self, timeout_seconds: float = 20.0) -> None:
        self._timeout = httpx.Timeout(timeout_seconds, connect=5.0)

    async def post_json(self, url: str, payload: dict[str, Any], correlation_id: str) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "X-Correlation-Id": correlation_id,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            if not response.content:
                return {"status": "accepted_without_body"}
            return response.json()
