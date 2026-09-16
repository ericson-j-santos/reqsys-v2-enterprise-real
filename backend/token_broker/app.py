from __future__ import annotations

import logging
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import FastAPI, Header, HTTPException, status
from jwt import PyJWKClient
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .bootstrap import GitHubAppBootstrap, load_persisted_app_credentials

logger = logging.getLogger("reqsys.token_broker")


class BrokerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BROKER_", extra="ignore")

    audience: str = "reqsys-copilot-agent-token-broker"
    allowed_repository: str = "ericson-j-santos/reqsys-v2-enterprise-real"
    allowed_workflow_ref: str = (
        "ericson-j-santos/reqsys-v2-enterprise-real/.github/workflows/"
        "pending-development-orchestrator.yml@refs/heads/main"
    )
    allowed_ref: str = "refs/heads/main"
    allowed_events: str = "workflow_dispatch,schedule"

    github_app_client_id: str = ""
    github_app_client_secret: str = ""
    github_app_refresh_token_bootstrap: str = ""

    token_state_encryption_key: str = ""
    token_state_db_path: str = "./data/copilot-agent-token-broker.db"
    refresh_skew_seconds: int = 300
    request_timeout_seconds: float = 15.0

    bootstrap_enabled: bool = False
    public_base_url: str = ""
    github_app_name: str = "ReqSys Copilot Agent Token Broker"
    github_app_manifest_permission: str = "agent_tasks"
    bootstrap_state_ttl_seconds: int = 900

    oidc_issuer: str = "https://token.actions.githubusercontent.com"
    oidc_jwks_url: str = "https://token.actions.githubusercontent.com/.well-known/jwks"
    github_oauth_token_url: str = "https://github.com/login/oauth/access_token"
    github_manifest_conversion_url: str = "https://api.github.com/app-manifests/{code}/conversions"
    github_app_manifest_url: str = "https://github.com/settings/apps/new"
    github_app_install_url: str = "https://github.com/apps/{slug}/installations/new"

    @property
    def allowed_event_set(self) -> set[str]:
        return {item.strip() for item in self.allowed_events.split(",") if item.strip()}


class TokenRequest(BaseModel):
    repository: str
    correlation_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._:/-]+$")


class TokenResponse(BaseModel):
    access_token: str


@dataclass(frozen=True)
class TokenState:
    refresh_token: str
    access_token: str | None = None
    access_expires_at: int | None = None
    refresh_expires_at: int | None = None


class BrokerNotReady(RuntimeError):
    pass


class OIDCValidationError(RuntimeError):
    pass


class OIDCVerifier(Protocol):
    def verify(self, token: str) -> dict[str, object]: ...


class TokenProvider(Protocol):
    def get_access_token(self) -> str: ...


class GitHubActionsOIDCVerifier:
    def __init__(self, settings: BrokerSettings) -> None:
        self.settings = settings
        self.jwks = PyJWKClient(settings.oidc_jwks_url)

    def verify(self, token: str) -> dict[str, object]:
        try:
            signing_key = self.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.settings.audience,
                issuer=self.settings.oidc_issuer,
                options={"require": ["exp", "iat", "iss", "aud", "repository", "workflow_ref", "ref", "event_name"]},
            )
        except Exception as exc:  # noqa: BLE001 - every JWT/JWKS error must fail closed
            raise OIDCValidationError("oidc_validation_failed") from exc

        expected = {
            "repository": self.settings.allowed_repository,
            "workflow_ref": self.settings.allowed_workflow_ref,
            "ref": self.settings.allowed_ref,
        }
        for claim, value in expected.items():
            if claims.get(claim) != value:
                raise OIDCValidationError(f"oidc_claim_rejected:{claim}")
        if claims.get("event_name") not in self.settings.allowed_event_set:
            raise OIDCValidationError("oidc_claim_rejected:event_name")
        return claims


class SQLiteEncryptedTokenStore:
    def __init__(self, db_path: str, encryption_key: str) -> None:
        if not encryption_key:
            raise BrokerNotReady("missing_token_state_encryption_key")
        try:
            self.fernet = Fernet(encryption_key.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise BrokerNotReady("invalid_token_state_encryption_key") from exc
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS token_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    refresh_token BLOB NOT NULL,
                    access_token BLOB NULL,
                    access_expires_at INTEGER NULL,
                    refresh_expires_at INTEGER NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )

    def _encrypt(self, value: str | None) -> bytes | None:
        return self.fernet.encrypt(value.encode("utf-8")) if value else None

    def _decrypt(self, value: bytes | None) -> str | None:
        if value is None:
            return None
        try:
            return self.fernet.decrypt(value).decode("utf-8")
        except InvalidToken as exc:
            raise BrokerNotReady("token_state_decryption_failed") from exc

    def load(self, conn: sqlite3.Connection | None = None) -> TokenState | None:
        owns = conn is None
        active = conn or self._connect()
        try:
            row = active.execute(
                "SELECT refresh_token, access_token, access_expires_at, refresh_expires_at FROM token_state WHERE id = 1"
            ).fetchone()
            if row is None:
                return None
            return TokenState(
                refresh_token=self._decrypt(row["refresh_token"]) or "",
                access_token=self._decrypt(row["access_token"]),
                access_expires_at=row["access_expires_at"],
                refresh_expires_at=row["refresh_expires_at"],
            )
        finally:
            if owns:
                active.close()

    def seed_refresh_token(self, refresh_token: str) -> None:
        if not refresh_token:
            return
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM token_state WHERE id = 1").fetchone() is None:
                conn.execute(
                    "INSERT INTO token_state(id, refresh_token, access_token, access_expires_at, refresh_expires_at, updated_at) VALUES(1, ?, NULL, NULL, NULL, ?)",
                    (self._encrypt(refresh_token), int(time.time())),
                )
            conn.commit()

    def replace(self, conn: sqlite3.Connection, state: TokenState) -> None:
        conn.execute(
            """
            INSERT INTO token_state(id, refresh_token, access_token, access_expires_at, refresh_expires_at, updated_at)
            VALUES(1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              refresh_token=excluded.refresh_token,
              access_token=excluded.access_token,
              access_expires_at=excluded.access_expires_at,
              refresh_expires_at=excluded.refresh_expires_at,
              updated_at=excluded.updated_at
            """,
            (
                self._encrypt(state.refresh_token),
                self._encrypt(state.access_token),
                state.access_expires_at,
                state.refresh_expires_at,
                int(time.time()),
            ),
        )

    def transaction(self) -> sqlite3.Connection:
        conn = self._connect()
        conn.execute("BEGIN IMMEDIATE")
        return conn


class GitHubUserTokenProvider:
    def __init__(
        self,
        settings: BrokerSettings,
        store: SQLiteEncryptedTokenStore,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.client_id = client_id or settings.github_app_client_id
        self.client_secret = client_secret or settings.github_app_client_secret
        self._lock = threading.Lock()

    def _refresh(self, refresh_token: str) -> TokenState:
        try:
            response = httpx.post(
                self.settings.github_oauth_token_url,
                headers={"Accept": "application/json"},
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=self.settings.request_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise BrokerNotReady("github_refresh_unavailable") from exc

        if response.status_code != 200:
            raise BrokerNotReady("github_refresh_rejected")
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("response is not an object")
            access_token = str(payload.get("access_token") or "")
            next_refresh_token = str(payload.get("refresh_token") or "")
            expires_in = int(payload.get("expires_in") or 0)
            refresh_expires_in = int(payload.get("refresh_token_expires_in") or 0)
        except (ValueError, TypeError, AttributeError) as exc:
            raise BrokerNotReady("github_refresh_invalid_response") from exc

        if not access_token or not next_refresh_token:
            raise BrokerNotReady("github_refresh_invalid_response")
        if expires_in <= 0 or refresh_expires_in <= 0:
            raise BrokerNotReady("github_refresh_invalid_expiry")

        now = int(time.time())
        return TokenState(
            refresh_token=next_refresh_token,
            access_token=access_token,
            access_expires_at=now + expires_in,
            refresh_expires_at=now + refresh_expires_in,
        )

    def get_access_token(self) -> str:
        if not self.client_id or not self.client_secret:
            raise BrokerNotReady("github_app_not_configured")

        with self._lock:
            conn = self.store.transaction()
            try:
                state = self.store.load(conn)
                if state is None or not state.refresh_token:
                    raise BrokerNotReady("github_app_authorization_required")
                now = int(time.time())
                if state.refresh_expires_at and state.refresh_expires_at <= now:
                    raise BrokerNotReady("github_refresh_token_expired")
                if state.access_token and state.access_expires_at and state.access_expires_at > now + self.settings.refresh_skew_seconds:
                    conn.commit()
                    return state.access_token

                refreshed = self._refresh(state.refresh_token)
                self.store.replace(conn, refreshed)
                conn.commit()
                return refreshed.access_token or ""
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()


@dataclass
class BrokerRuntime:
    settings: BrokerSettings
    verifier: OIDCVerifier | None
    token_provider: TokenProvider | None
    not_ready_reason: str | None = None


def build_runtime(settings: BrokerSettings | None = None) -> BrokerRuntime:
    cfg = settings or BrokerSettings()
    if not cfg.token_state_encryption_key:
        return BrokerRuntime(cfg, None, None, "missing_token_state_encryption_key")
    try:
        store = SQLiteEncryptedTokenStore(cfg.token_state_db_path, cfg.token_state_encryption_key)
        client_id = cfg.github_app_client_id
        client_secret = cfg.github_app_client_secret
        if not client_id or not client_secret:
            persisted = load_persisted_app_credentials(
                cfg.token_state_db_path,
                cfg.token_state_encryption_key,
            )
            if persisted is not None:
                client_id = persisted.client_id
                client_secret = persisted.client_secret
        if not client_id or not client_secret:
            return BrokerRuntime(cfg, None, None, "github_app_not_configured")

        store.seed_refresh_token(cfg.github_app_refresh_token_bootstrap)
        verifier = GitHubActionsOIDCVerifier(cfg)
        state = store.load()
        if state is None or not state.refresh_token:
            return BrokerRuntime(cfg, verifier, None, "github_app_authorization_required")
        provider = GitHubUserTokenProvider(cfg, store, client_id, client_secret)
        return BrokerRuntime(cfg, verifier, provider)
    except BrokerNotReady as exc:
        return BrokerRuntime(cfg, None, None, str(exc))


class RuntimeManager:
    def __init__(
        self,
        settings: BrokerSettings,
        initial_runtime: BrokerRuntime | None = None,
    ) -> None:
        self.settings = settings
        self._lock = threading.Lock()
        self._runtime = initial_runtime or build_runtime(settings)

    def current(self) -> BrokerRuntime:
        return self._runtime

    def refresh(self) -> BrokerRuntime:
        with self._lock:
            self._runtime = build_runtime(self.settings)
            return self._runtime


def _bearer_token(header: str | None) -> str:
    if not header or not re.match(r"^Bearer\s+\S+$", header, flags=re.IGNORECASE):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_or_invalid_bearer")
    return header.split(None, 1)[1]


def create_app(
    runtime: BrokerRuntime | None = None,
    settings: BrokerSettings | None = None,
) -> FastAPI:
    cfg = settings or (runtime.settings if runtime else BrokerSettings())
    manager = RuntimeManager(cfg, runtime)
    app = FastAPI(title="ReqSys Copilot Agent Token Broker", version="1.1.0")
    app.state.runtime_manager = manager
    GitHubAppBootstrap(cfg, manager.refresh).register(app)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        active = manager.current()
        if active.not_ready_reason or not active.verifier or not active.token_provider:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="bootstrap_required")
        return {"status": "ready"}

    @app.post("/token", response_model=TokenResponse)
    def issue_token(payload: TokenRequest, authorization: str | None = Header(default=None)) -> TokenResponse:
        active = manager.current()
        if active.not_ready_reason or not active.verifier or not active.token_provider:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="bootstrap_required")
        if payload.repository != active.settings.allowed_repository:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="repository_rejected")

        raw = _bearer_token(authorization)
        try:
            active.verifier.verify(raw)
        except OIDCValidationError as exc:
            logger.warning("OIDC request rejected correlation_id=%s reason=%s", payload.correlation_id, str(exc))
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="oidc_rejected") from exc

        try:
            token = active.token_provider.get_access_token()
        except BrokerNotReady as exc:
            logger.error("Token issuance unavailable correlation_id=%s reason=%s", payload.correlation_id, str(exc))
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="token_unavailable") from exc
        if not token:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="token_unavailable")
        logger.info("Token issued correlation_id=%s repository=%s", payload.correlation_id, payload.repository)
        return TokenResponse(access_token=token)

    return app


app = create_app()
