from __future__ import annotations

import hashlib
import html
import json
import re
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import quote, urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Cookie, FastAPI, HTTPException, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse


INSTALL_STATE_COOKIE = "reqsys_github_app_install_state"
GITHUB_OAUTH_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_USER_INSTALLATION_REPOS_URL = (
    "https://api.github.com/user/installations/{installation_id}/repositories"
)


class BootstrapSettings(Protocol):
    bootstrap_enabled: bool
    public_base_url: str
    github_app_name: str
    github_app_manifest_permission: str
    bootstrap_state_ttl_seconds: int
    token_state_encryption_key: str
    token_state_db_path: str
    request_timeout_seconds: float
    allowed_repository: str
    github_oauth_token_url: str
    github_manifest_conversion_url: str
    github_app_manifest_url: str
    github_app_install_url: str


@dataclass(frozen=True)
class AppCredentials:
    app_id: int
    slug: str
    client_id: str
    client_secret: str


@dataclass(frozen=True)
class AuthorizedTokenState:
    refresh_token: str
    access_token: str
    access_expires_at: int
    refresh_expires_at: int


class BootstrapError(RuntimeError):
    pass


class BootstrapStore:
    def __init__(self, db_path: str, encryption_key: str) -> None:
        if not encryption_key:
            raise BootstrapError("missing_token_state_encryption_key")
        try:
            self.fernet = Fernet(encryption_key.encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise BootstrapError("invalid_token_state_encryption_key") from exc
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS token_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    refresh_token BLOB NOT NULL,
                    access_token BLOB NULL,
                    access_expires_at INTEGER NULL,
                    refresh_expires_at INTEGER NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS app_credentials (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    app_id INTEGER NOT NULL,
                    slug TEXT NOT NULL,
                    client_id BLOB NOT NULL,
                    client_secret BLOB NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bootstrap_state (
                    state_hash TEXT PRIMARY KEY,
                    purpose TEXT NOT NULL,
                    context TEXT NULL,
                    expires_at INTEGER NOT NULL,
                    consumed_at INTEGER NULL,
                    created_at INTEGER NOT NULL
                );
                """
            )
            columns = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(bootstrap_state)").fetchall()
            }
            if "context" not in columns:
                conn.execute("ALTER TABLE bootstrap_state ADD COLUMN context TEXT NULL")
            conn.commit()

    def _encrypt(self, value: str) -> bytes:
        return self.fernet.encrypt(value.encode("utf-8"))

    def _decrypt(self, value: bytes) -> str:
        try:
            return self.fernet.decrypt(value).decode("utf-8")
        except InvalidToken as exc:
            raise BootstrapError("bootstrap_state_decryption_failed") from exc

    @staticmethod
    def _state_hash(raw_state: str) -> str:
        return hashlib.sha256(raw_state.encode("utf-8")).hexdigest()

    def create_state(
        self,
        purpose: str,
        ttl_seconds: int,
        context: str | None = None,
    ) -> str:
        if ttl_seconds <= 0:
            raise BootstrapError("invalid_bootstrap_state_ttl")
        raw_state = secrets.token_urlsafe(32)
        now = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO bootstrap_state(
                    state_hash, purpose, context, expires_at, consumed_at, created_at
                ) VALUES(?, ?, ?, ?, NULL, ?)
                """,
                (
                    self._state_hash(raw_state),
                    purpose,
                    context,
                    now + ttl_seconds,
                    now,
                ),
            )
            conn.commit()
        return raw_state

    def consume_state(self, raw_state: str, purpose: str) -> str | None:
        if not raw_state:
            raise BootstrapError("missing_bootstrap_state")
        state_hash = self._state_hash(raw_state)
        now = int(time.time())
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT purpose, context, expires_at, consumed_at
                FROM bootstrap_state
                WHERE state_hash = ?
                """,
                (state_hash,),
            ).fetchone()
            if (
                row is None
                or row["purpose"] != purpose
                or row["consumed_at"] is not None
                or int(row["expires_at"]) < now
            ):
                conn.rollback()
                raise BootstrapError("bootstrap_state_rejected")
            conn.execute(
                "UPDATE bootstrap_state SET consumed_at = ? WHERE state_hash = ?",
                (now, state_hash),
            )
            conn.commit()
            return str(row["context"]) if row["context"] is not None else None

    def save_app_credentials(self, credentials: AppCredentials) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO app_credentials(id, app_id, slug, client_id, client_secret, updated_at)
                VALUES(1, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    app_id=excluded.app_id,
                    slug=excluded.slug,
                    client_id=excluded.client_id,
                    client_secret=excluded.client_secret,
                    updated_at=excluded.updated_at
                """,
                (
                    credentials.app_id,
                    credentials.slug,
                    self._encrypt(credentials.client_id),
                    self._encrypt(credentials.client_secret),
                    int(time.time()),
                ),
            )
            conn.commit()

    def load_app_credentials(self) -> AppCredentials | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT app_id, slug, client_id, client_secret FROM app_credentials WHERE id = 1"
            ).fetchone()
        if row is None:
            return None
        client_id = self._decrypt(row["client_id"])
        client_secret = self._decrypt(row["client_secret"])
        if not client_id or not client_secret:
            raise BootstrapError("github_app_credentials_invalid")
        return AppCredentials(
            app_id=int(row["app_id"]),
            slug=str(row["slug"]),
            client_id=client_id,
            client_secret=client_secret,
        )

    def has_authorized_tokens(self) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM token_state WHERE id = 1 LIMIT 1"
            ).fetchone()
        return row is not None

    def save_authorized_tokens(self, token_state: AuthorizedTokenState) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
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
                    self._encrypt(token_state.refresh_token),
                    self._encrypt(token_state.access_token),
                    token_state.access_expires_at,
                    token_state.refresh_expires_at,
                    int(time.time()),
                ),
            )
            conn.commit()


def load_persisted_app_credentials(
    db_path: str,
    encryption_key: str,
) -> AppCredentials | None:
    if not encryption_key:
        return None
    try:
        return BootstrapStore(db_path, encryption_key).load_app_credentials()
    except BootstrapError:
        return None


class GitHubAppBootstrap:
    def __init__(
        self,
        settings: BootstrapSettings,
        on_authorized: Callable[[], object],
    ) -> None:
        self.settings = settings
        self.on_authorized = on_authorized

    @property
    def base_url(self) -> str:
        return self.settings.public_base_url.rstrip("/")

    @property
    def oauth_callback_url(self) -> str:
        return f"{self.base_url}/bootstrap/github-app/oauth/callback"

    @property
    def install_callback_url(self) -> str:
        return f"{self.base_url}/bootstrap/github-app/install/callback"

    def _require_enabled(self) -> BootstrapStore:
        if not self.settings.bootstrap_enabled:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
        if not self.base_url.startswith("https://"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="bootstrap_not_configured",
            )
        if not re.fullmatch(r"[a-z0-9_]+", self.settings.github_app_manifest_permission):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="bootstrap_not_configured",
            )
        try:
            return BootstrapStore(
                self.settings.token_state_db_path,
                self.settings.token_state_encryption_key,
            )
        except BootstrapError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="bootstrap_not_configured",
            ) from exc

    def _manifest(self) -> dict[str, object]:
        return {
            "name": self.settings.github_app_name,
            "url": self.base_url,
            "redirect_url": f"{self.base_url}/bootstrap/github-app/manifest/callback",
            "callback_urls": [self.oauth_callback_url],
            "setup_url": self.install_callback_url,
            "setup_on_update": False,
            "public": False,
            "request_oauth_on_install": False,
            "default_permissions": {
                self.settings.github_app_manifest_permission: "write",
            },
            "default_events": [],
        }

    @staticmethod
    def _parse_manifest_credentials(payload: object) -> AppCredentials:
        if not isinstance(payload, dict):
            raise BootstrapError("github_manifest_invalid_response")
        try:
            credentials = AppCredentials(
                app_id=int(payload.get("id") or 0),
                slug=str(payload.get("slug") or ""),
                client_id=str(payload.get("client_id") or ""),
                client_secret=str(payload.get("client_secret") or ""),
            )
        except (TypeError, ValueError, AttributeError) as exc:
            raise BootstrapError("github_manifest_invalid_response") from exc
        if (
            credentials.app_id <= 0
            or not credentials.slug
            or not credentials.client_id
            or not credentials.client_secret
        ):
            raise BootstrapError("github_manifest_invalid_response")
        return credentials

    @staticmethod
    def _parse_oauth_tokens(payload: object) -> AuthorizedTokenState:
        if not isinstance(payload, dict):
            raise BootstrapError("github_oauth_invalid_response")
        try:
            access_token = str(payload.get("access_token") or "")
            refresh_token = str(payload.get("refresh_token") or "")
            expires_in = int(payload.get("expires_in") or 0)
            refresh_expires_in = int(payload.get("refresh_token_expires_in") or 0)
        except (TypeError, ValueError, AttributeError) as exc:
            raise BootstrapError("github_oauth_invalid_response") from exc
        if not access_token or not refresh_token or expires_in <= 0 or refresh_expires_in <= 0:
            raise BootstrapError("github_oauth_invalid_response")
        now = int(time.time())
        return AuthorizedTokenState(
            refresh_token=refresh_token,
            access_token=access_token,
            access_expires_at=now + expires_in,
            refresh_expires_at=now + refresh_expires_in,
        )

    def _verify_repository_installation(
        self,
        access_token: str,
        installation_id: int,
    ) -> None:
        url = GITHUB_USER_INSTALLATION_REPOS_URL.format(
            installation_id=installation_id
        )
        page = 1
        while page <= 100:
            try:
                response = httpx.get(
                    url,
                    headers={
                        "Accept": "application/vnd.github+json",
                        "Authorization": f"Bearer {access_token}",
                        "X-GitHub-Api-Version": "2026-03-10",
                    },
                    params={"per_page": 100, "page": page},
                    timeout=self.settings.request_timeout_seconds,
                )
            except httpx.HTTPError as exc:
                raise BootstrapError("github_installation_verification_unavailable") from exc
            if response.status_code != 200:
                raise BootstrapError("github_installation_verification_rejected")
            try:
                payload = response.json()
                repositories = payload.get("repositories") if isinstance(payload, dict) else None
                total_count = payload.get("total_count") if isinstance(payload, dict) else None
            except (ValueError, TypeError, AttributeError) as exc:
                raise BootstrapError("github_installation_verification_invalid_response") from exc
            if not isinstance(repositories, list):
                raise BootstrapError("github_installation_verification_invalid_response")
            if isinstance(total_count, int) and total_count != 1:
                raise BootstrapError("github_app_repository_scope_too_broad")
            for repository in repositories:
                if (
                    isinstance(repository, dict)
                    and repository.get("full_name") == self.settings.allowed_repository
                ):
                    return
            if len(repositories) < 100:
                break
            page += 1
        raise BootstrapError("github_app_repository_access_required")

    def register(self, app: FastAPI) -> None:
        @app.get("/bootstrap/github-app", response_class=HTMLResponse)
        def bootstrap_start() -> HTMLResponse:
            store = self._require_enabled()
            if store.has_authorized_tokens():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="github_app_already_authorized",
                )
            csrf_state = store.create_state(
                "manifest",
                self.settings.bootstrap_state_ttl_seconds,
            )
            manifest_json = json.dumps(self._manifest(), separators=(",", ":"))
            action = f"{self.settings.github_app_manifest_url}?{urlencode({'state': csrf_state})}"
            body = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                "<title>ReqSys GitHub App Bootstrap</title></head><body>"
                "<h1>ReqSys GitHub App Bootstrap</h1>"
                "<p>Continue no GitHub para criar, instalar e autorizar a App. Segredos não são exibidos.</p>"
                f"<form method='post' action='{html.escape(action, quote=True)}'>"
                f"<input type='hidden' name='manifest' value='{html.escape(manifest_json, quote=True)}'>"
                "<button type='submit'>Create GitHub App</button></form></body></html>"
            )
            return HTMLResponse(
                content=body,
                status_code=200,
                headers={"Cache-Control": "no-store"},
            )

        @app.get("/bootstrap/github-app/manifest/callback")
        def manifest_callback(
            code: str = Query(min_length=1, max_length=500),
            csrf_state: str = Query(alias="state", min_length=1, max_length=500),
        ) -> RedirectResponse:
            store = self._require_enabled()
            try:
                store.consume_state(csrf_state, "manifest")
            except BootstrapError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="bootstrap_state_rejected",
                ) from exc
            if not code.isalnum():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="github_manifest_code_rejected",
                )

            conversion_url = self.settings.github_manifest_conversion_url.format(
                code=quote(code, safe="")
            )
            try:
                response = httpx.post(
                    conversion_url,
                    headers={
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2026-03-10",
                    },
                    timeout=self.settings.request_timeout_seconds,
                )
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="github_manifest_unavailable",
                ) from exc
            if response.status_code != 201:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="github_manifest_rejected",
                )
            try:
                credentials = self._parse_manifest_credentials(response.json())
            except BootstrapError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="github_manifest_invalid_response",
                ) from exc

            store.save_app_credentials(credentials)
            install_state = store.create_state(
                "installation",
                self.settings.bootstrap_state_ttl_seconds,
            )
            install_url = self.settings.github_app_install_url.format(
                slug=quote(credentials.slug, safe="")
            )
            redirect = RedirectResponse(url=install_url, status_code=303)
            redirect.set_cookie(
                key=INSTALL_STATE_COOKIE,
                value=install_state,
                max_age=self.settings.bootstrap_state_ttl_seconds,
                httponly=True,
                secure=True,
                samesite="lax",
                path="/bootstrap/github-app/install/callback",
            )
            return redirect

        @app.get("/bootstrap/github-app/install/callback")
        def install_callback(
            installation_id: int = Query(gt=0),
            install_state: str | None = Cookie(default=None, alias=INSTALL_STATE_COOKIE),
        ) -> RedirectResponse:
            store = self._require_enabled()
            try:
                store.consume_state(install_state or "", "installation")
                credentials = store.load_app_credentials()
            except BootstrapError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="bootstrap_state_rejected",
                ) from exc
            if credentials is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="github_app_not_configured",
                )

            oauth_state = store.create_state(
                "oauth",
                self.settings.bootstrap_state_ttl_seconds,
                context=str(installation_id),
            )
            authorize_url = f"{GITHUB_OAUTH_AUTHORIZE_URL}?{urlencode({'client_id': credentials.client_id, 'redirect_uri': self.oauth_callback_url, 'state': oauth_state})}"
            redirect = RedirectResponse(url=authorize_url, status_code=303)
            redirect.delete_cookie(
                key=INSTALL_STATE_COOKIE,
                path="/bootstrap/github-app/install/callback",
            )
            return redirect

        @app.get("/bootstrap/github-app/oauth/callback", response_class=HTMLResponse)
        def oauth_callback(
            code: str = Query(min_length=1, max_length=500),
            csrf_state: str = Query(alias="state", min_length=1, max_length=500),
        ) -> HTMLResponse:
            store = self._require_enabled()
            try:
                installation_context = store.consume_state(csrf_state, "oauth")
                installation_id = int(installation_context or "0")
                credentials = store.load_app_credentials()
            except (BootstrapError, TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="bootstrap_state_rejected",
                ) from exc
            if installation_id <= 0 or credentials is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="github_app_not_configured",
                )

            try:
                response = httpx.post(
                    self.settings.github_oauth_token_url,
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": credentials.client_id,
                        "client_secret": credentials.client_secret,
                        "code": code,
                        "redirect_uri": self.oauth_callback_url,
                    },
                    timeout=self.settings.request_timeout_seconds,
                )
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="github_oauth_unavailable",
                ) from exc
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="github_oauth_rejected",
                )
            try:
                token_state = self._parse_oauth_tokens(response.json())
                self._verify_repository_installation(
                    token_state.access_token,
                    installation_id,
                )
            except BootstrapError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=str(exc),
                ) from exc

            store.save_authorized_tokens(token_state)
            self.on_authorized()
            body = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                "<title>ReqSys Broker Ready</title></head><body>"
                "<h1>Autorização concluída</h1>"
                "<p>O estado foi persistido de forma cifrada. Segredos não são exibidos.</p>"
                "<p>O próximo passo é validar /readyz e executar o E2E governado da issue #1677.</p>"
                "</body></html>"
            )
            return HTMLResponse(
                content=body,
                status_code=200,
                headers={"Cache-Control": "no-store"},
            )
