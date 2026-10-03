from __future__ import annotations

from scripts.capture_fly_environment_state import CommandResult, capture_environment


def manifest() -> dict:
    return {
        "environments": {
            "dev": {
                "api_app": "reqsys-api-dev",
                "frontend_app": "reqsys-app-dev",
                "fly_config": "backend/fly.dev.toml",
                "backend_fly_config": "backend/fly.dev.toml",
                "frontend_fly_config": "frontend/fly.dev.toml",
                "min_machines_running": 1,
                "required_secret_names": ["JWT_SECRET", "JWT_ISSUER", "JWT_AUDIENCE"],
            }
        }
    }


def payload_for(command: list[str], *, missing_secret: bool = False):
    if "status" in command:
        return {"Machines": [{"id": "m1", "region": "gru", "state": "started"}]}
    if command[1:3] == ["config", "show"]:
        return {
            "app": command[-1] if "--app" in command else (
                "reqsys-api-dev" if "backend" in command[-1] else "reqsys-app-dev"
            ),
            "primary_region": "gru",
            "env": {"APP_ENV": "development", "ALLOW_DEMO_LOGIN": "true"},
            "http_service": {"internal_port": 8000, "force_https": True, "min_machines_running": 1},
        }
    if "secrets" in command:
        names = ["JWT_SECRET", "JWT_ISSUER", "JWT_AUDIENCE"]
        if missing_secret:
            names.remove("JWT_AUDIENCE")
        return [{"Name": name, "DeploymentStatus": "Deployed", "Digest": "not-persisted"} for name in names]
    if "releases" in command:
        return [{"Version": 4, "Status": "complete", "CreatedAt": "2026-07-31T00:00:00Z"}]
    if "checks" in command:
        return [{"Name": "health", "Status": "passing"}]
    raise AssertionError(command)


def runner(missing_secret: bool = False):
    def run(command: list[str], _timeout: int) -> CommandResult:
        return CommandResult(True, payload_for(command, missing_secret=missing_secret), None, command)

    return run


def test_ready_capture_is_sanitized() -> None:
    report = capture_environment(
        manifest=manifest(),
        environment="dev",
        expected_sha="abcdef1234567890",
        phase="read_only",
        runner=runner(),
        observed_at_epoch=1,
    )

    assert report["ready"] is True
    assert report["api"]["regions"] == ["gru"]
    assert report["api"]["machine_count"] == 1
    assert report["secret_values_persisted"] is False
    assert all("Digest" not in item for item in report["api"]["secrets"])
    assert report["blocking_issues"] == []


def test_missing_required_secret_blocks_capture() -> None:
    report = capture_environment(
        manifest=manifest(),
        environment="dev",
        expected_sha="abcdef123456",
        phase="read_only",
        runner=runner(missing_secret=True),
        observed_at_epoch=1,
    )

    assert report["ready"] is False
    assert "api:required_secret_missing:JWT_AUDIENCE" in report["blocking_issues"]


def test_failed_command_is_fail_closed() -> None:
    def failing(command: list[str], _timeout: int) -> CommandResult:
        if "status" in command:
            return CommandResult(False, None, "unavailable", command)
        return CommandResult(True, payload_for(command), None, command)

    report = capture_environment(
        manifest=manifest(),
        environment="dev",
        expected_sha="abcdef123456",
        phase="read_only",
        runner=failing,
        observed_at_epoch=1,
    )

    assert report["ready"] is False
    assert any("command_failed:status" in item for item in report["blocking_issues"])
