from __future__ import annotations

import json

from scripts import copilot_agent_token_provider as provider


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_direct_secret_remains_break_glass_compatible() -> None:
    result = provider.resolve_copilot_agent_token(
        repository="owner/repo",
        environ={"COPILOT_AGENT_TOKEN": "direct-token"},
    )
    assert result.available is True
    assert result.token == "direct-token"
    assert result.source == "repository_secret"


def test_missing_broker_fails_closed_without_token() -> None:
    result = provider.resolve_copilot_agent_token(repository="owner/repo", environ={})
    assert result.available is False
    assert result.token == ""
    assert result.reason == "broker_not_configured"


def test_oidc_broker_exchanges_short_lived_token_without_refresh_secret() -> None:
    requests = []

    def opener(request, timeout):
        requests.append((request, timeout))
        if len(requests) == 1:
            return FakeResponse({"value": "oidc-jwt"})
        return FakeResponse({"access_token": "ghu-short-lived"})

    result = provider.resolve_copilot_agent_token(
        repository="owner/repo",
        correlation_id="run-123",
        environ={
            "COPILOT_AGENT_TOKEN_BROKER_URL": "https://broker.example/token",
            "ACTIONS_ID_TOKEN_REQUEST_URL": "https://oidc.example/token?x=1",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "actions-runtime-token",
        },
        opener=opener,
    )

    assert result.available is True
    assert result.token == "ghu-short-lived"
    assert result.source == "oidc_broker"
    oidc_request = requests[0][0]
    assert "audience=reqsys-copilot-agent-token-broker" in oidc_request.full_url
    broker_request = requests[1][0]
    assert broker_request.full_url == "https://broker.example/token"
    assert broker_request.get_header("Authorization") == "Bearer oidc-jwt"
    body = json.loads(broker_request.data.decode("utf-8"))
    assert body == {"repository": "owner/repo", "correlation_id": "run-123"}


def test_non_https_broker_fails_closed() -> None:
    def opener(request, timeout):
        return FakeResponse({"value": "oidc-jwt"})

    result = provider.resolve_copilot_agent_token(
        repository="owner/repo",
        environ={
            "COPILOT_AGENT_TOKEN_BROKER_URL": "http://broker.example/token",
            "ACTIONS_ID_TOKEN_REQUEST_URL": "https://oidc.example/token?x=1",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "runtime-token",
        },
        opener=opener,
    )
    assert result.available is False
    assert result.reason == "oidc_broker_exchange_failed"


def test_provider_does_not_return_oidc_runtime_token_on_failure() -> None:
    def opener(request, timeout):
        raise ValueError("simulated failure")

    result = provider.resolve_copilot_agent_token(
        repository="owner/repo",
        environ={
            "COPILOT_AGENT_TOKEN_BROKER_URL": "https://broker.example/token",
            "ACTIONS_ID_TOKEN_REQUEST_URL": "https://oidc.example/token?x=1",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "must-not-escape",
        },
        opener=opener,
    )
    assert result.token == ""
    assert "must-not-escape" not in result.reason
