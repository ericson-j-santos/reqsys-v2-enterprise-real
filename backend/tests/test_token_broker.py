from __future__ import annotations

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from token_broker import app as broker


class AcceptingVerifier:
    def verify(self, token: str) -> dict[str, object]:
        assert token == "oidc-token"
        return {"repository": "ericson-j-santos/reqsys-v2-enterprise-real"}


class RejectingVerifier:
    def verify(self, token: str) -> dict[str, object]:
        raise broker.OIDCValidationError("oidc_claim_rejected:repository")


class StaticTokenProvider:
    def __init__(self, token: str = "short-lived-token") -> None:
        self.token = token
        self.calls = 0

    def get_access_token(self) -> str:
        self.calls += 1
        return self.token


def _client(verifier=None, provider=None) -> TestClient:
    settings = broker.BrokerSettings(
        github_app_client_id="client-id",
        github_app_client_secret="client-secret",
        token_state_encryption_key=Fernet.generate_key().decode("ascii"),
    )
    runtime = broker.BrokerRuntime(
        settings=settings,
        verifier=verifier or AcceptingVerifier(),
        token_provider=provider or StaticTokenProvider(),
    )
    return TestClient(broker.create_app(runtime))


def test_health_is_available_while_bootstrap_is_pending() -> None:
    runtime = broker.BrokerRuntime(broker.BrokerSettings(), None, None, "github_app_not_configured")
    client = TestClient(broker.create_app(runtime))

    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").status_code == 503
    assert client.post(
        "/token",
        headers={"Authorization": "Bearer oidc-token"},
        json={"repository": "ericson-j-santos/reqsys-v2-enterprise-real", "correlation_id": "case-1"},
    ).status_code == 503


def test_token_endpoint_requires_bearer() -> None:
    client = _client()
    response = client.post(
        "/token",
        json={"repository": "ericson-j-santos/reqsys-v2-enterprise-real", "correlation_id": "case-2"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "missing_or_invalid_bearer"


def test_token_endpoint_rejects_repository_before_credential_use() -> None:
    provider = StaticTokenProvider()
    client = _client(provider=provider)
    response = client.post(
        "/token",
        headers={"Authorization": "Bearer oidc-token"},
        json={"repository": "other/repo", "correlation_id": "case-3"},
    )
    assert response.status_code == 403
    assert provider.calls == 0


def test_token_endpoint_rejects_invalid_oidc() -> None:
    provider = StaticTokenProvider()
    client = _client(verifier=RejectingVerifier(), provider=provider)
    response = client.post(
        "/token",
        headers={"Authorization": "Bearer oidc-token"},
        json={"repository": "ericson-j-santos/reqsys-v2-enterprise-real", "correlation_id": "case-4"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "oidc_rejected"
    assert provider.calls == 0


def test_token_endpoint_returns_only_access_token() -> None:
    provider = StaticTokenProvider()
    client = _client(provider=provider)
    response = client.post(
        "/token",
        headers={"Authorization": "Bearer oidc-token"},
        json={"repository": "ericson-j-santos/reqsys-v2-enterprise-real", "correlation_id": "case-5"},
    )
    assert response.status_code == 200
    assert response.json() == {"access_token": "short-lived-token"}
    assert provider.calls == 1


def test_refresh_rotates_once_and_persists_only_ciphertext(tmp_path, monkeypatch) -> None:
    key = Fernet.generate_key().decode("ascii")
    db_path = tmp_path / "broker.db"
    settings = broker.BrokerSettings(
        github_app_client_id="client-id",
        github_app_client_secret="client-secret",
        token_state_encryption_key=key,
        token_state_db_path=str(db_path),
        refresh_skew_seconds=60,
    )
    store = broker.SQLiteEncryptedTokenStore(str(db_path), key)
    store.seed_refresh_token("refresh-old")
    calls = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {
                "access_token": "access-new",
                "expires_in": 28_800,
                "refresh_token": "refresh-new",
                "refresh_token_expires_in": 15_552_000,
            }

    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    monkeypatch.setattr(broker.httpx, "post", fake_post)
    provider = broker.GitHubUserTokenProvider(settings, store)

    assert provider.get_access_token() == "access-new"
    assert provider.get_access_token() == "access-new"
    assert len(calls) == 1

    state = store.load()
    assert state is not None
    assert state.refresh_token == "refresh-new"
    assert state.access_token == "access-new"
    raw = db_path.read_bytes()
    assert b"refresh-old" not in raw
    assert b"refresh-new" not in raw
    assert b"access-new" not in raw
