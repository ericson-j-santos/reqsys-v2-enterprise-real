#!/usr/bin/env python3
"""Resolve a short-lived GitHub user token for Agent Tasks without logging secrets.

Priority:
1. Existing COPILOT_AGENT_TOKEN (break-glass/bootstrap compatibility).
2. OIDC-authenticated external broker, configured by COPILOT_AGENT_TOKEN_BROKER_URL.

The broker is expected to validate the GitHub Actions OIDC JWT (issuer, audience,
repository/ref/workflow claims) and return a short-lived GitHub App user access
token. Token lifecycle/refresh stays outside GitHub Actions, so refresh tokens do
not need to be copied into repository secrets.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

DEFAULT_AUDIENCE = "reqsys-copilot-agent-token-broker"


@dataclass(frozen=True)
class TokenResolution:
    token: str = ""
    source: str = "none"
    reason: str = "unavailable"

    @property
    def available(self) -> bool:
        return bool(self.token)


def _with_audience(url: str, audience: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["audience"] = audience
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _read_json(response: Any) -> dict[str, Any]:
    raw = response.read().decode("utf-8")
    payload = json.loads(raw) if raw else {}
    if not isinstance(payload, dict):
        raise ValueError("JSON object expected")
    return payload


def request_actions_oidc_token(
    request_url: str,
    request_token: str,
    audience: str,
    *,
    opener: Any = urlopen,
) -> str:
    if not request_url or not request_token:
        raise ValueError("GitHub Actions OIDC environment unavailable")
    request = Request(
        _with_audience(request_url, audience),
        method="GET",
        headers={
            "Authorization": f"Bearer {request_token}",
            "Accept": "application/json",
        },
    )
    with opener(request, timeout=15) as response:
        value = str(_read_json(response).get("value") or "")
    if not value:
        raise ValueError("OIDC provider returned no token")
    return value


def exchange_oidc_for_agent_token(
    broker_url: str,
    oidc_token: str,
    *,
    repository: str,
    correlation_id: str,
    opener: Any = urlopen,
) -> str:
    if not broker_url.lower().startswith("https://"):
        raise ValueError("broker URL must use HTTPS")
    payload = json.dumps(
        {"repository": repository, "correlation_id": correlation_id},
        separators=(",", ":"),
    ).encode("utf-8")
    request = Request(
        broker_url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {oidc_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with opener(request, timeout=20) as response:
        token = str(_read_json(response).get("access_token") or "")
    if not token:
        raise ValueError("token broker returned no access token")
    return token


def resolve_copilot_agent_token(
    *,
    repository: str,
    correlation_id: str = "",
    environ: Mapping[str, str] | None = None,
    opener: Any = urlopen,
) -> TokenResolution:
    env = os.environ if environ is None else environ
    direct = str(env.get("COPILOT_AGENT_TOKEN") or "")
    if direct:
        return TokenResolution(direct, "repository_secret", "direct_token_available")

    broker_url = str(env.get("COPILOT_AGENT_TOKEN_BROKER_URL") or "").strip()
    if not broker_url:
        return TokenResolution(reason="broker_not_configured")

    audience = str(env.get("COPILOT_AGENT_TOKEN_BROKER_AUDIENCE") or DEFAULT_AUDIENCE).strip()
    try:
        oidc_token = request_actions_oidc_token(
            str(env.get("ACTIONS_ID_TOKEN_REQUEST_URL") or ""),
            str(env.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN") or ""),
            audience,
            opener=opener,
        )
        token = exchange_oidc_for_agent_token(
            broker_url,
            oidc_token,
            repository=repository,
            correlation_id=correlation_id,
            opener=opener,
        )
        return TokenResolution(token, "oidc_broker", "short_lived_user_token_issued")
    except (HTTPError, URLError, ValueError, json.JSONDecodeError):
        # Fail closed and deliberately avoid exception bodies: providers can echo
        # sensitive request data in errors. The orchestrator can use its governed
        # local fallback when this route is unavailable.
        return TokenResolution(reason="oidc_broker_exchange_failed")
