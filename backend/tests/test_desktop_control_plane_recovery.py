from __future__ import annotations

import urllib.error
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services import desktop_control_plane_recovery as recovery


def _set_environment(monkeypatch, value: str = "development") -> None:
    monkeypatch.setattr(
        recovery,
        "settings",
        SimpleNamespace(normalized_environment=value),
    )


def _comment(
    comment_id: object,
    now: datetime,
    *,
    body: str | None = None,
    actor: str | None = None,
    association: str | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> dict:
    timestamp = now.isoformat().replace("+00:00", "Z")
    return {
        "id": comment_id,
        "body": recovery.COMMAND if body is None else body,
        "user": {"login": recovery.EXPECTED_ACTOR if actor is None else actor},
        "author_association": (
            recovery.EXPECTED_ASSOCIATION if association is None else association
        ),
        "created_at": timestamp if created_at is None else created_at,
        "updated_at": timestamp if updated_at is None else updated_at,
    }


def test_normalization_clock_and_secret_resolution(monkeypatch) -> None:
    assert recovery._normalize_correlation_id("  corr-12345678  ") == "corr-12345678"
    with pytest.raises(recovery.DesktopRecoveryDispatchError, match="correlation_id_invalid"):
        recovery._normalize_correlation_id("short")

    observed = recovery._now()
    assert observed.tzinfo is UTC

    monkeypatch.setattr(
        recovery,
        "get_secret",
        lambda name, default="": "primary-token" if name == "GITHUB_TOKEN" else default,
    )
    assert recovery._github_token() == "primary-token"

    monkeypatch.setattr(
        recovery,
        "get_secret",
        lambda name, default="": "fallback-token" if name == "GITHUB_PAT" else default,
    )
    assert recovery._github_token() == "fallback-token"

    monkeypatch.setattr(recovery, "get_secret", lambda *_args, **_kwargs: "")
    with pytest.raises(recovery.DesktopRecoveryDispatchError, match="github_auth_unavailable"):
        recovery._github_token()


def test_github_json_success_and_fail_closed_transport(monkeypatch) -> None:
    class Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"id": 42}'

    captured = {}

    def urlopen_ok(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(recovery.urllib.request, "urlopen", urlopen_ok)
    status_code, payload = recovery._github_json(
        "POST",
        "https://api.github.com/example",
        "secret-token",
        {"body": recovery.COMMAND},
    )
    assert status_code == 201
    assert payload == {"id": 42}
    assert captured["timeout"] == 10.0
    assert captured["request"].get_method() == "POST"

    def urlopen_http_error(_request, timeout):
        assert timeout == 10.0
        raise urllib.error.HTTPError(
            "https://api.github.com/example",
            403,
            "forbidden",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(recovery.urllib.request, "urlopen", urlopen_http_error)
    with pytest.raises(recovery.DesktopRecoveryDispatchError, match="github_http_403"):
        recovery._github_json("GET", "https://api.github.com/example", "secret-token")

    def urlopen_transport_error(_request, timeout):
        assert timeout == 10.0
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(recovery.urllib.request, "urlopen", urlopen_transport_error)
    with pytest.raises(
        recovery.DesktopRecoveryDispatchError,
        match="github_transport_unavailable",
    ):
        recovery._github_json("GET", "https://api.github.com/example", "secret-token")


def test_parse_time_and_reusable_comment_filters() -> None:
    now = datetime(2026, 9, 24, 22, 10, tzinfo=UTC)

    assert recovery._parse_github_time("") is None
    assert recovery._parse_github_time("not-a-date") is None
    assert recovery._parse_github_time("2026-09-24T22:10:00") is None
    assert recovery._parse_github_time("2026-09-24T22:10:00Z") == now
    assert recovery._reusable_comment({"not": "a-list"}, now) is None

    edited = _comment(7, now)
    edited["updated_at"] = (now + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")

    comments = [
        "not-a-dict",
        _comment(1, now, actor="someone-else"),
        _comment(2, now, association="MEMBER"),
        _comment(3, now, body="/desktop-runtime admin other"),
        _comment(4, now, created_at="", updated_at=""),
        edited,
        _comment(5, now - timedelta(seconds=recovery.MAX_REUSE_AGE_SECONDS + 1)),
        _comment(6, now + timedelta(seconds=61)),
        _comment("invalid-id", now),
        _comment(-1, now),
        _comment(42, now - timedelta(seconds=10)),
        _comment(41, now - timedelta(seconds=20)),
    ]
    assert recovery._reusable_comment(comments, now) == 42


def test_dispatch_reuses_fresh_command_without_post(monkeypatch) -> None:
    _set_environment(monkeypatch)
    now = datetime(2026, 9, 24, 22, 10, tzinfo=UTC)
    calls = []

    def transport(method, url, token, payload):
        calls.append((method, url, token, payload))
        assert method == "GET"
        return 200, [_comment(1234, now - timedelta(seconds=30))]

    result = recovery.dispatch_control_plane_recovery(
        "corr-backend-reuse-001",
        transport=transport,
        now=now,
        token="token",
    )

    assert result["accepted"] is True
    assert result["broker_comment_id"] == 1234
    assert result["broker_correlation_id"] == "desktop-admin-gh-comment-1234"
    assert result["reused_fresh_command"] is True
    assert result["arbitrary_command_supported"] is False
    assert result["remote_shell_used"] is False
    assert result["production_touched"] is False
    assert result["secrets_exposed"] is False
    assert [call[0] for call in calls] == ["GET"]


def test_dispatch_creates_only_fixed_command_when_reuse_is_unavailable(monkeypatch) -> None:
    _set_environment(monkeypatch, "dev")
    now = datetime(2026, 9, 24, 22, 10, tzinfo=UTC)
    calls = []

    def transport(method, url, token, payload):
        calls.append((method, url, token, payload))
        if method == "GET":
            return 200, []
        assert method == "POST"
        assert payload == {"body": recovery.COMMAND}
        return 201, {"id": 5678}

    result = recovery.dispatch_control_plane_recovery(
        "corr-backend-create-001",
        transport=transport,
        now=now,
        token="token",
    )

    assert result["broker_comment_id"] == 5678
    assert result["reused_fresh_command"] is False
    assert [call[0] for call in calls] == ["GET", "POST"]


@pytest.mark.parametrize("environment", ["production", "staging", "homologation"])
def test_dispatch_blocks_non_dev_before_transport(monkeypatch, environment) -> None:
    _set_environment(monkeypatch, environment)
    with pytest.raises(recovery.DesktopRecoveryDispatchError, match="environment_not_allowed"):
        recovery.dispatch_control_plane_recovery(
            "corr-backend-block-001",
            transport=lambda *_args: pytest.fail("transport must not be called"),
            token="token",
        )


def test_dispatch_rejects_empty_token_before_transport(monkeypatch) -> None:
    _set_environment(monkeypatch)
    with pytest.raises(recovery.DesktopRecoveryDispatchError, match="github_auth_unavailable"):
        recovery.dispatch_control_plane_recovery(
            "corr-backend-token-001",
            transport=lambda *_args: pytest.fail("transport must not be called"),
            token=" ",
        )


def test_dispatch_fails_closed_on_comment_lookup(monkeypatch) -> None:
    _set_environment(monkeypatch)
    with pytest.raises(
        recovery.DesktopRecoveryDispatchError,
        match="github_comment_lookup_failed",
    ):
        recovery.dispatch_control_plane_recovery(
            "corr-backend-lookup-001",
            transport=lambda *_args: (500, []),
            token="token",
        )


@pytest.mark.parametrize(
    ("create_status", "created", "expected_error"),
    [
        (200, {"id": 1}, "github_comment_create_failed"),
        (201, "unexpected", "github_comment_create_failed"),
        (201, {"id": "invalid"}, "github_comment_id_missing"),
        (201, {"id": 0}, "github_comment_id_missing"),
    ],
)
def test_dispatch_fails_closed_on_invalid_comment_creation(
    monkeypatch,
    create_status,
    created,
    expected_error,
) -> None:
    _set_environment(monkeypatch)

    def transport(method, _url, _token, _payload):
        if method == "GET":
            return 200, []
        return create_status, created

    with pytest.raises(recovery.DesktopRecoveryDispatchError, match=expected_error):
        recovery.dispatch_control_plane_recovery(
            "corr-backend-create-fail-001",
            transport=transport,
            token="token",
        )
