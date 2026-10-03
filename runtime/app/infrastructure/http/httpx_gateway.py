from __future__ import annotations

from typing import Any

import httpx


class HttpxGateway:
    def __init__(
        self,
        timeout_seconds: float = 20.0,
        service_token: str = "",
        service_token_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout = httpx.Timeout(timeout_seconds, connect=5.0)
        self._service_token = service_token.strip()
        self._service_token_url = service_token_url.rstrip("/") if service_token_url else None
        self._transport = transport

    def _headers(self, url: str, correlation_id: str) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-Correlation-Id": correlation_id,
        }
        if (
            self._service_token
            and self._service_token_url
            and url.rstrip("/") == self._service_token_url
        ):
            headers["X-Service-Token"] = self._service_token
        return headers

    async def post_json(self, url: str, payload: dict[str, Any], correlation_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._headers(url, correlation_id),
            )
            response.raise_for_status()
            if not response.content:
                return {"status": "accepted_without_body"}
            return response.json()
