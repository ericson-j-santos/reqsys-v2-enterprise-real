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
    client = TestClient(broker.create_app(settings=settings), base_url="https://broker.example")
    post_calls: list[str] = []
    get_calls: list[str] = []

    class Response:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_post(url, *args, **kwargs):
        post_calls.append(str(url))
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

    def fake_get(url, *args, **kwargs):
        get_calls.append(str(url))
        return Response(
            200,
            {
                "total_count": 1,
                "repositories": [
                    {"full_name": "ericson-j-santos/reqsys-v2-enterprise-real"}
                ],
            },
        )

    monkeypatch.setattr(bootstrap_module.httpx, "post", fake_post)
    monkeypatch.setattr(bootstrap_module.httpx, "get", fake_get)

    start = client.get("/bootstrap/github-app")
    assert start.status_code == 200
    assert "Create GitHub App" in start.text
    assert "agent_tasks" in start.text
    assert 'request_oauth_on_install&quot;:false' in start.text
    assert "bootstrap/github-app/install/callback" in start.text
    assert "client-secret-value" not in start.text
    manifest_state = _manifest_state(start.text)

    manifest_callback = client.get(
        "/bootstrap/github-app/manifest/callback",
        params={"code": "manifestcode123", "state": manifest_state},
        follow_redirects=False,
    )
    assert manifest_callback.status_code == 303
    assert manifest_callback.headers["location"] == (
        "https://github.com/apps/reqsys-copilot-agent-token-broker/installations/new"
    )
    assert bootstrap_module.INSTALL_STATE_COOKIE in client.cookies

    install_callback = client.get(
        "/bootstrap/github-app/install/callback",
        params={"installation_id": 456},
        follow_redirects=False,
    )
    assert install_callback.status_code == 303
    authorize_url = urlparse(install_callback.headers["location"])
    assert f"{authorize_url.scheme}://{authorize_url.netloc}{authorize_url.path}" == (
        "https://github.com/login/oauth/authorize"
    )
    authorize_params = parse_qs(authorize_url.query)
    assert authorize_params["client_id"] == ["client-id-secretish"]
    assert authorize_params["redirect_uri"] == [
        "https://broker.example/bootstrap/github-app/oauth/callback"
    ]
    oauth_state = authorize_params["state"][0]
    assert bootstrap_module.INSTALL_STATE_COOKIE not in client.cookies

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
    assert len(post_calls) == 2
    assert get_calls == [
        "https://api.github.com/user/installations/456/repositories"
    ]

    replay = client.get(
        "/bootstrap/github-app/oauth/callback",
        params={"code": "oauth-code-replay", "state": oauth_state},
    )
    assert replay.status_code == 400
    assert replay.json()["detail"] == "bootstrap_state_rejected"
    assert len(post_calls) == 2
    assert len(get_calls) == 1


def test_oauth_does_not_become_ready_without_reqsys_repository_access(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    client = TestClient(broker.create_app(settings=settings), base_url="https://broker.example")

    class Response:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_post(url, *args, **kwargs):
        if "app-manifests" in str(url):
            return Response(
                201,
                {
                    "id": 123,
                    "slug": "reqsys-copilot-agent-token-broker",
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                },
            )
        return Response(
            200,
            {
                "access_token": "access-token",
                "expires_in": 28_800,
                "refresh_token": "refresh-token",
                "refresh_token_expires_in": 15_552_000,
            },
        )

    monkeypatch.setattr(bootstrap_module.httpx, "post", fake_post)
    monkeypatch.setattr(
        bootstrap_module.httpx,
        "get",
        lambda *args, **kwargs: Response(
            200,
            {"repositories": [{"full_name": "ericson-j-santos/another-repo"}]},
        ),
    )

    start = client.get("/bootstrap/github-app")
    manifest_state = _manifest_state(start.text)
    manifest_callback = client.get(
        "/bootstrap/github-app/manifest/callback",
        params={"code": "manifestcode123", "state": manifest_state},
        follow_redirects=False,
    )
    assert manifest_callback.status_code == 303

    install_callback = client.get(
        "/bootstrap/github-app/install/callback",
        params={"installation_id": 456},
        follow_redirects=False,
    )
    oauth_state = parse_qs(urlparse(install_callback.headers["location"]).query)["state"][0]

    oauth_callback = client.get(
        "/bootstrap/github-app/oauth/callback",
        params={"code": "oauth-code", "state": oauth_state},
    )
    assert oauth_callback.status_code == 502
    assert oauth_callback.json()["detail"] == "github_app_repository_access_required"
    assert client.get("/readyz").status_code == 503

    raw_db = (tmp_path / "broker.db").read_bytes()
    assert b"access-token" not in raw_db
    assert b"refresh-token" not in raw_db


def test_manifest_callback_rejects_unknown_state_before_network_call(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    client = TestClient(broker.create_app(settings=settings), base_url="https://broker.example")
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


def test_manifest_callback_rejects_non_alphanumeric_code_before_network_call(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    client = TestClient(broker.create_app(settings=settings), base_url="https://broker.example")
    called = False

    def fake_post(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("network must not be called")

    monkeypatch.setattr(bootstrap_module.httpx, "post", fake_post)
    start = client.get("/bootstrap/github-app")
    manifest_state = _manifest_state(start.text)

    response = client.get(
        "/bootstrap/github-app/manifest/callback",
        params={"code": "../metadata", "state": manifest_state},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "github_manifest_code_rejected"
    assert called is False


def test_bootstrap_cannot_restart_after_authorization(tmp_path) -> None:
    settings = _settings(tmp_path)
    store = bootstrap_module.BootstrapStore(
        settings.token_state_db_path,
        settings.token_state_encryption_key,
    )
    store.save_authorized_tokens(
        bootstrap_module.AuthorizedTokenState(
            refresh_token="refresh-token",
            access_token="access-token",
            access_expires_at=1,
            refresh_expires_at=2,
        )
    )
    client = TestClient(broker.create_app(settings=settings), base_url="https://broker.example")

    response = client.get("/bootstrap/github-app")

    assert response.status_code == 409
    assert response.json()["detail"] == "github_app_already_authorized"


def test_oauth_rejects_installation_scope_broader_than_target_repository(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    client = TestClient(broker.create_app(settings=settings), base_url="https://broker.example")

    class Response:
        def __init__(self, status_code: int, payload: dict[str, object]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_post(url, *args, **kwargs):
        if "app-manifests" in str(url):
            return Response(
                201,
                {
                    "id": 123,
                    "slug": "reqsys-copilot-agent-token-broker",
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                },
            )
        return Response(
            200,
            {
                "access_token": "access-token",
                "expires_in": 28_800,
                "refresh_token": "refresh-token",
                "refresh_token_expires_in": 15_552_000,
            },
        )

    monkeypatch.setattr(bootstrap_module.httpx, "post", fake_post)
    monkeypatch.setattr(
        bootstrap_module.httpx,
        "get",
        lambda *args, **kwargs: Response(
            200,
            {
                "total_count": 2,
                "repositories": [
                    {"full_name": "ericson-j-santos/reqsys-v2-enterprise-real"},
                    {"full_name": "ericson-j-santos/another-repo"},
                ],
            },
        ),
    )

    start = client.get("/bootstrap/github-app")
    manifest_state = _manifest_state(start.text)
    manifest_callback = client.get(
        "/bootstrap/github-app/manifest/callback",
        params={"code": "manifestcode123", "state": manifest_state},
        follow_redirects=False,
    )
    assert manifest_callback.status_code == 303

    install_callback = client.get(
        "/bootstrap/github-app/install/callback",
        params={"installation_id": 456},
        follow_redirects=False,
    )
    oauth_state = parse_qs(urlparse(install_callback.headers["location"]).query)["state"][0]

    oauth_callback = client.get(
        "/bootstrap/github-app/oauth/callback",
        params={"code": "oauth-code", "state": oauth_state},
    )

    assert oauth_callback.status_code == 502
    assert oauth_callback.json()["detail"] == "github_app_repository_scope_too_broad"
    assert client.get("/readyz").status_code == 503
