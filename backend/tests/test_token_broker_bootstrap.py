from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from token_broker import app as broker
from token_broker import bootstrap as bootstrap_module


def _settings(tmp_path) -> broker.BrokerSettings:
    return broker.BrokerSettings(
        bootstrap_enabled=True,
        public_base_url="https://broker.example",
        token_state_encryption_key=Fernet.generate_key().decode("ascii"),
        token_state_db_path=str(tmp_path / "broker.db"),
    )


def _manifest_state(body: str) -> str:
    match = re.search(r"settings/apps/new\?state=([^'&]+)", body)
    assert match is not None
    return match.group(1)


def test_bootstrap_is_hidden_when_disabled(tmp_path) -> None:
    settings = broker.BrokerSettings(
        token_state_encryption_key=Fernet.generate_key().decode("ascii"),
        token_state_db_path=str(tmp_path / "broker.db"),
    )
    client = TestClient(broker.create_app(settings=settings))

    response = client.get("/bootstrap/github-app")

    assert response.status_code == 404


def test_bootstrap_requires_https_public_base_url(tmp_path) -> None:
    settings = broker.BrokerSettings(
        bootstrap_enabled=True,
        public_base_url="http://broker.example",
        token_state_encryption_key=Fernet.generate_key().decode("ascii"),
        token_state_db_path=str(tmp_path / "broker.db"),
    )
    client = TestClient(broker.create_app(settings=settings))

    response = client.get("/bootstrap/github-app")

    assert response.status_code == 503
    assert response.json()["detail"] == "bootstrap_not_configured"


def test_manifest_bootstrap_rotates_to_ready_without_exposing_secrets(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    client = TestClient(broker.create_app(settings=settings))
    calls: list[str] = []

    class Response:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_post(url, *args, **kwargs):
        calls.append(str(url))
        if "app-manifests" in str(url):
            return Response(
                201,
                {
                    "id": 123,
                    "slug": "reqsys-copilot-agent-token-broker",
                    "client_id": "client-id-secretish",
                    "client_secret": "client-secret-value",
                    "pem": "private-key-that-must-be-discarded",
                    "webhook_secret": "webhook-secret-that-must-be-discarded",
                },
            )
        return Response(
            200,
            {
                "access_token": "access-token-value",
                "expires_in": 28_800,
                "refresh_token": "refresh-token-value",
                "refresh_token_expires_in": 15_552_000,
            },
        )

    monkeypatch.setattr(bootstrap_module.httpx, "post", fake_post)

    start = client.get("/bootstrap/github-app")
    assert start.status_code == 200
    assert "Create GitHub App" in start.text
    assert "agent_tasks" in start.text
    assert "client-secret-value" not in start.text
    manifest_state = _manifest_state(start.text)

    manifest_callback = client.get(
        "/bootstrap/github-app/manifest/callback",
        params={"code": "manifest-code", "state": manifest_state},
        follow_redirects=False,
    )
    assert manifest_callback.status_code == 303
    location = manifest_callback.headers["location"]
    assert location.startswith(
        "https://github.com/apps/reqsys-copilot-agent-token-broker/installations/new?"
    )
    oauth_state = parse_qs(urlparse(location).query)["state"][0]

    oauth_callback = client.get(
        "/bootstrap/github-app/oauth/callback",
        params={"code": "oauth-code", "state": oauth_state},
    )
    assert oauth_callback.status_code == 200
    assert "Autorização concluída" in oauth_callback.text
    assert "access-token-value" not in oauth_callback.text
    assert "refresh-token-value" not in oauth_callback.text
    assert client.get("/readyz").status_code == 200

    raw_db = (tmp_path / "broker.db").read_bytes()
    assert b"client-secret-value" not in raw_db
    assert b"access-token-value" not in raw_db
    assert b"refresh-token-value" not in raw_db
    assert b"private-key-that-must-be-discarded" not in raw_db
    assert b"webhook-secret-that-must-be-discarded" not in raw_db
    assert len(calls) == 2

    replay = client.get(
        "/bootstrap/github-app/oauth/callback",
        params={"code": "oauth-code-replay", "state": oauth_state},
    )
    assert replay.status_code == 400
    assert replay.json()["detail"] == "bootstrap_state_rejected"
    assert len(calls) == 2


def test_manifest_callback_rejects_unknown_state_before_network_call(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    client = TestClient(broker.create_app(settings=settings))
    called = False

    def fake_post(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("network must not be called")

    monkeypatch.setattr(bootstrap_module.httpx, "post", fake_post)

    response = client.get(
        "/bootstrap/github-app/manifest/callback",
        params={"code": "manifest-code", "state": "unknown-state"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "bootstrap_state_rejected"
    assert called is False
