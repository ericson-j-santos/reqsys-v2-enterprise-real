from __future__ import annotations

import json
from pathlib import Path

from scripts import worker_pool_native_preflight as probe

SHA = "a" * 40
REQUEST_ID = "026e9c5add6137dc65e673a6"


def environment(path: str) -> dict[str, str]:
    return {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": probe.REPOSITORY,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": SHA,
        "CODEX_WORKER_POOL_API_TOKEN_FILE_HOST": path,
    }


def test_existing_reference_and_healthy_loopback_are_preflight_only(tmp_path: Path) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("private-fixture-must-never-appear", encoding="utf-8")
    result = probe.inspect(
        environment(str(token_file)), hostname="Noteri", expected_sha=SHA,
        request_id=REQUEST_ID, health=lambda: "healthy",
    )
    assert result["status"] == "PRECHECK_READY_FOR_AUTHENTICATED_HANDOFF"
    assert result["token_reference"] == "file_present_unread"
    assert result["authenticated_handoff_proven"] is False
    assert result["task_enqueued"] is False
    assert result["secrets_read"] is False
    assert result["state_changed"] is False
    encoded = json.dumps(result)
    assert "private-fixture-must-never-appear" not in encoded
    assert str(token_file) not in encoded


def test_missing_reference_fails_closed_even_when_health_is_positive() -> None:
    env = environment("")
    calls = []
    result = probe.inspect(
        env, hostname="Noteri", expected_sha=SHA, request_id=REQUEST_ID,
        health=lambda: calls.append("GET") or "healthy",
    )
    assert result["status"] == "BLOCKED_TOKEN_REFERENCE"
    assert result["token_reference"] == "missing"
    assert result["pool_health"] == "healthy"
    assert calls == ["GET"]


def test_nonabsolute_token_reference_rejected() -> None:
    result = probe.inspect(
        environment("secrets/token"), hostname="Noteri", expected_sha=SHA,
        request_id=REQUEST_ID, health=lambda: "healthy",
    )
    assert result["token_reference"] == "invalid"
    assert result["status"] == "BLOCKED_TOKEN_REFERENCE"


def test_symlink_reference_rejected(tmp_path: Path) -> None:
    target = tmp_path / "token"
    target.write_text("fixture", encoding="utf-8")
    alias = tmp_path / "alias"
    alias.symlink_to(target)
    result = probe.inspect(
        environment(str(alias)), hostname="Noteri", expected_sha=SHA,
        request_id=REQUEST_ID, health=lambda: "healthy",
    )
    assert result["token_reference"] == "invalid"


def test_missing_or_directory_reference_rejected(tmp_path: Path) -> None:
    for path in (tmp_path, tmp_path / "not-present"):
        result = probe.inspect(
            environment(str(path)), hostname="Noteri", expected_sha=SHA,
            request_id=REQUEST_ID, health=lambda: "healthy",
        )
        assert result["token_reference"] == "file_unavailable"
        assert result["status"] == "BLOCKED_TOKEN_REFERENCE"


def test_nonhealthy_runtime_never_qualifies_authentication(tmp_path: Path) -> None:
    token = tmp_path / "token"
    token.write_text("fixture", encoding="utf-8")
    for value in ("not_ready", "unreachable", "invalid_response", "invented"):
        result = probe.inspect(
            environment(str(token)), hostname="Noteri", expected_sha=SHA,
            request_id=REQUEST_ID, health=lambda v=value: v,
        )
        assert result["status"] == "BLOCKED_NATIVE_POOL_HEALTH"
        assert result["authenticated_handoff_proven"] is False


def test_incorrect_host_sha_and_request_block_before_network() -> None:
    for host, sha, request in (
        ("DESKTOP-PDQK954", SHA, REQUEST_ID),
        ("Noteri", "b" * 40, REQUEST_ID),
        ("Noteri", SHA, "unexpected"),
    ):
        result = probe.inspect(
            environment("unused"), hostname=host, expected_sha=sha,
            request_id=request, health=lambda: (_ for _ in ()).throw(
                AssertionError("no HTTP before context verification")
            ),
        )
        assert result["status"] == "BLOCKED_EXECUTION_CONTEXT"


def test_incorrect_repository_branch_or_actions_context_blocks() -> None:
    for field, value in (
        ("GITHUB_REPOSITORY", "other/repo"),
        ("GITHUB_REF", "refs/heads/feature"),
        ("GITHUB_ACTIONS", "false"),
    ):
        env = environment("unused")
        env[field] = value
        report = probe.inspect(
            env, hostname="Noteri", expected_sha=SHA, request_id=REQUEST_ID,
            health=lambda: (_ for _ in ()).throw(AssertionError("unexpected HTTP")),
        )
        assert report["status"] == "BLOCKED_EXECUTION_CONTEXT"


def test_legacy_service_file_environment_is_read_only(tmp_path: Path) -> None:
    token = tmp_path / "token"
    token.write_text("fixture", encoding="utf-8")
    env = environment("")
    env["CODEX_WORKER_POOL_API_TOKEN_FILE"] = str(token)
    report = probe.inspect(
        env, hostname="Noteri", expected_sha=SHA, request_id=REQUEST_ID,
        health=lambda: "healthy",
    )
    assert report["token_reference"] == "file_present_unread"


def test_http_health_uses_exact_loopback_without_redirect(monkeypatch) -> None:
    class Response:
        status = 200

        def read(self, length):
            assert length == 4097
            return (
                b'{"status":"healthy","auth_configured":true,'
                b'"expected_rules_sha_configured":true}'
            )

    class Connection:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("127.0.0.1", 8097, 3)

        def request(self, method, path, headers):
            assert (method, path) == ("GET", "/health")
            assert headers == {"Accept": "application/json"}

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(probe.http.client, "HTTPConnection", Connection)
    assert probe.health_probe() == "healthy"


def test_http_health_200_without_auth_configuration_fails_closed(monkeypatch) -> None:
    class Response:
        status = 200

        def read(self, length):
            return b'{"status":"healthy","auth_configured":false}'

    class Connection:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(probe.http.client, "HTTPConnection", Connection)
    assert probe.health_probe() == "not_ready"
