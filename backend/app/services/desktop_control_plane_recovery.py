from __future__ import annotations

import http.client
import json
import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from app.core.config import settings
from app.core.secrets import get_secret

REPOSITORY = "ericson-j-santos/desktop-pc24x7-runtime"
ISSUE_NUMBER = 2
EXPECTED_ACTOR = "ericson-j-santos"
EXPECTED_ASSOCIATION = "OWNER"
COMMAND = "/desktop-runtime admin recover-control-plane"
GITHUB_API_BASE = "https://api.github.com"
MAX_REUSE_AGE_SECONDS = 240
DEV_ENVIRONMENTS = {"development", "dev", "desenvolvimento"}


class DesktopRecoveryDispatchError(RuntimeError):
    def __init__(self, code: str, *, http_status: int = 503):
        super().__init__(code)
        self.code = code
        self.http_status = http_status


GithubTransport = Callable[[str, str, str, dict[str, Any] | None], tuple[int, Any]]


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_correlation_id(value: str) -> str:
    normalized = str(value or "").strip()
    if not 8 <= len(normalized) <= 160:
        raise DesktopRecoveryDispatchError("correlation_id_invalid", http_status=422)
    return normalized


def _github_token() -> str:
    token = (
        get_secret("GITHUB_TOKEN", "") or
        get_secret("GITHUB_PAT", "") or
        ""
    ).strip()
    if not token:
        raise DesktopRecoveryDispatchError("github_auth_unavailable", http_status=503)
    return token


def _ensure_dev() -> None:
    environment = str(settings.normalized_environment or "").strip().casefold()
    if environment not in DEV_ENVIRONMENTS:
        raise DesktopRecoveryDispatchError("environment_not_allowed", http_status=403)


def _github_json(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError:
        raise DesktopRecoveryDispatchError("github_url_not_allowed", http_status=503) from None

    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.github.com"
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise DesktopRecoveryDispatchError("github_url_not_allowed", http_status=503)

    target = parsed.path or "/"
    if parsed.query:
        target = f"{target}?{parsed.query}"

    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "ReqSys-Desktop-Control-Plane-Recovery/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
        **({"Content-Type": "application/json"} if body is not None else {}),
    }

    connection = http.client.HTTPSConnection("api.github.com", timeout=10.0)
    try:
        connection.request(method, target, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read().decode("utf-8")
        if int(response.status) >= 400:
            raise DesktopRecoveryDispatchError(
                f"github_http_{int(response.status)}",
                http_status=503,
            )
        data = json.loads(raw) if raw else None
        return int(response.status), data
    except DesktopRecoveryDispatchError:
        raise
    except (OSError, http.client.HTTPException, UnicodeDecodeError, json.JSONDecodeError):
        raise DesktopRecoveryDispatchError("github_transport_unavailable", http_status=503) from None
    finally:
        connection.close()

def _parse_github_time(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _reusable_comment(comments: Any, now: datetime) -> int | None:
    if not isinstance(comments, list):
        return None
    cutoff = now - timedelta(seconds=MAX_REUSE_AGE_SECONDS)
    candidates: list[int] = []
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        user = comment.get("user") or {}
        if str(user.get("login") or "").casefold() != EXPECTED_ACTOR.casefold():
            continue
        if str(comment.get("author_association") or "").upper() != EXPECTED_ASSOCIATION:
            continue
        if str(comment.get("body") or "").strip() != COMMAND:
            continue
        created = _parse_github_time(comment.get("created_at"))
        updated = _parse_github_time(comment.get("updated_at"))
        if created is None or updated is None or created != updated:
            continue
        if created < cutoff or created > now + timedelta(seconds=60):
            continue
        try:
            comment_id = int(comment.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if comment_id > 0:
            candidates.append(comment_id)
    return max(candidates) if candidates else None


def dispatch_control_plane_recovery(
    correlation_id: str,
    *,
    transport: GithubTransport = _github_json,
    now: datetime | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    request_correlation_id = _normalize_correlation_id(correlation_id)
    _ensure_dev()
    github_token = token.strip() if token is not None else _github_token()
    if not github_token:
        raise DesktopRecoveryDispatchError("github_auth_unavailable", http_status=503)

    observed_at = now or _now()
    since = urllib.parse.quote(
        (observed_at - timedelta(seconds=MAX_REUSE_AGE_SECONDS))
        .isoformat()
        .replace("+00:00", "Z")
    )
    comments_url = (
        f"{GITHUB_API_BASE}/repos/{REPOSITORY}/issues/{ISSUE_NUMBER}/comments"
        f"?since={since}&per_page=100"
    )
    status, comments = transport("GET", comments_url, github_token, None)
    if status != 200:
        raise DesktopRecoveryDispatchError("github_comment_lookup_failed", http_status=503)

    comment_id = _reusable_comment(comments, observed_at)
    reused = comment_id is not None

    if comment_id is None:
        create_url = f"{GITHUB_API_BASE}/repos/{REPOSITORY}/issues/{ISSUE_NUMBER}/comments"
        status, created = transport(
            "POST",
            create_url,
            github_token,
            {"body": COMMAND},
        )
        if status != 201 or not isinstance(created, dict):
            raise DesktopRecoveryDispatchError("github_comment_create_failed", http_status=503)
        try:
            comment_id = int(created.get("id") or 0)
        except (TypeError, ValueError):
            comment_id = 0
        if comment_id <= 0:
            raise DesktopRecoveryDispatchError("github_comment_id_missing", http_status=503)

    return {
        "schema_version": "1.0.0",
        "accepted": True,
        "environment": "dev",
        "target_host": "DESKTOP-PDQK954",
        "transport": "reqsys_dev_http_8083_to_desktop_runtime_broker",
        "request_correlation_id": request_correlation_id,
        "broker_comment_id": comment_id,
        "broker_correlation_id": f"desktop-admin-gh-comment-{comment_id}",
        "reused_fresh_command": reused,
        "command_contract": "desktop_runtime_recover_control_plane",
        "arbitrary_command_supported": False,
        "remote_shell_used": False,
        "production_touched": False,
        "secrets_exposed": False,
        "observed_at": observed_at.isoformat(),
    }
