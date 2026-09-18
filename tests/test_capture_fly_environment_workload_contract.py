"""Contract tests for the per-workload Fly evidence model (P0-C).

Before this contract existed the collector reused the environment level
``min_machines_running`` (an API-scoped value) for the frontend as well, which
made ``frontend:machines_below_minimum`` a structural outcome for a workload
that is scale-to-zero by design. These tests pin the corrected model and its
fail-closed controls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.capture_fly_environment_state import CommandResult, capture_environment

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "infra" / "fly-environments.json"


def manifest(
    *,
    frontend_type: str = "scale_to_zero",
    frontend_min: int = 0,
) -> dict:
    return {
        "environments": {
            "dev": {
                "api_app": "reqsys-api-dev",
                "frontend_app": "reqsys-app-dev",
                "fly_config": "backend/fly.dev.toml",
                "backend_fly_config": "backend/fly.dev.toml",
                "frontend_fly_config": "frontend/fly.dev.toml",
                "min_machines_running": 1,
                "workload_contracts": {
                    "api": {"workload_type": "always_on", "min_machines_running": 1},
                    "frontend": {
                        "workload_type": frontend_type,
                        "min_machines_running": frontend_min,
                    },
                },
                "required_secret_names": ["JWT_SECRET"],
            }
        }
    }


def _is_frontend(command: list[str]) -> bool:
    return any("app-dev" in part or "frontend/" in part for part in command)


def payload_for(
    command: list[str],
    *,
    frontend_machine_state: str | None = "stopped",
    frontend_auto_start: bool = True,
    frontend_declared_min: int = 0,
) -> object:
    frontend = _is_frontend(command)
    if "status" in command:
        if frontend:
            if frontend_machine_state is None:
                return {"Machines": []}
            return {
                "Machines": [
                    {"id": "f1", "region": "gru", "state": frontend_machine_state}
                ]
            }
        return {"Machines": [{"id": "m1", "region": "gru", "state": "started"}]}
    if command[1:3] == ["config", "show"]:
        if frontend:
            return {
                "app": "reqsys-app-dev",
                "primary_region": "gru",
                "env": {},
                "http_service": {
                    "internal_port": 80,
                    "force_https": True,
                    "auto_start_machines": frontend_auto_start,
                    "auto_stop_machines": True,
                    "min_machines_running": frontend_declared_min,
                },
            }
        return {
            "app": "reqsys-api-dev",
            "primary_region": "gru",
            "env": {"APP_ENV": "development"},
            "http_service": {
                "internal_port": 8000,
                "force_https": True,
                "auto_start_machines": True,
                "auto_stop_machines": True,
                "min_machines_running": 1,
            },
        }
    if "secrets" in command:
        return [{"Name": "JWT_SECRET", "DeploymentStatus": "Deployed"}]
    if "releases" in command:
        return [{"Version": 4, "Status": "complete"}]
    if "checks" in command:
        return []
    raise AssertionError(command)


def runner(**kwargs):
    def run(command: list[str], _timeout: int) -> CommandResult:
        return CommandResult(True, payload_for(command, **kwargs), None, command)

    return run


def capture(manifest_payload: dict, **runner_kwargs) -> dict:
    return capture_environment(
        manifest=manifest_payload,
        environment="dev",
        expected_sha="abcdef1234567890",
        phase="post_deploy",
        runner=runner(**runner_kwargs),
        observed_at_epoch=1,
    )


# --- caso positivo -----------------------------------------------------------


def test_scale_to_zero_frontend_with_stopped_machine_is_ready() -> None:
    report = capture(manifest())

    assert report["ready"] is True, report["blocking_issues"]
    assert report["blocking_issues"] == []
    frontend = report["frontend"]["topology_evidence"]
    assert frontend["workload_type"] == "scale_to_zero"
    assert frontend["active_machine_count"] == 0
    assert frontend["stopped_machine_count"] == 1
    assert frontend["remote_auto_start_machines"] is True
    assert report["api"]["topology_evidence"]["workload_type"] == "always_on"
    assert report["api"]["topology_evidence"]["active_machine_count"] == 1


def test_scale_to_zero_frontend_with_running_machine_is_ready() -> None:
    report = capture(manifest(), frontend_machine_state="started")

    assert report["ready"] is True, report["blocking_issues"]
    assert report["frontend"]["topology_evidence"]["active_machine_count"] == 1


# --- casos negativos / fail-closed -------------------------------------------


def test_scale_to_zero_without_any_machine_blocks() -> None:
    report = capture(manifest(), frontend_machine_state=None)

    assert report["ready"] is False
    assert "frontend:scale_to_zero_without_machine" in report["blocking_issues"]


def test_scale_to_zero_with_autostart_disabled_blocks() -> None:
    report = capture(manifest(), frontend_auto_start=False)

    assert report["ready"] is False
    assert "frontend:scale_to_zero_autostart_disabled" in report["blocking_issues"]


def test_contract_diverging_from_fly_config_blocks() -> None:
    """Declaring scale-to-zero while the fly config demands a machine fails."""
    report = capture(manifest(), frontend_declared_min=1)

    assert report["ready"] is False
    assert "frontend:workload_contract_mismatch:1/0" in report["blocking_issues"]


def test_scale_to_zero_contract_with_nonzero_minimum_is_invalid() -> None:
    report = capture(
        manifest(frontend_type="scale_to_zero", frontend_min=2),
        frontend_declared_min=2,
    )

    assert report["ready"] is False
    assert (
        "frontend:workload_contract_invalid:scale_to_zero_requires_zero_minimum:2"
        in report["blocking_issues"]
    )


def test_unknown_workload_type_is_rejected() -> None:
    report = capture(manifest(frontend_type="best_effort", frontend_min=0))

    assert report["ready"] is False
    assert "frontend:workload_type_invalid:best_effort" in report["blocking_issues"]


# --- teste do próprio teste (controle) ---------------------------------------


def test_always_on_api_below_minimum_still_blocks() -> None:
    """The original control must remain active for always-on workloads."""

    def failing_runner(command: list[str], _timeout: int) -> CommandResult:
        if "status" in command and not _is_frontend(command):
            return CommandResult(True, {"Machines": []}, None, command)
        return CommandResult(True, payload_for(command), None, command)

    report = capture_environment(
        manifest=manifest(),
        environment="dev",
        expected_sha="abcdef1234567890",
        phase="post_deploy",
        runner=failing_runner,
        observed_at_epoch=1,
    )

    assert report["ready"] is False
    assert "api:machines_below_minimum:0/1" in report["blocking_issues"]


# --- coerência do manifesto versionado ---------------------------------------


@pytest.mark.parametrize("environment", ["dev", "hml", "prod"])
def test_versioned_manifest_declares_both_workload_contracts(environment: str) -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contracts = payload["environments"][environment]["workload_contracts"]

    assert set(contracts) == {"api", "frontend"}
    for role, contract in contracts.items():
        assert contract["workload_type"] in {"always_on", "scale_to_zero"}
        minimum = contract["min_machines_running"]
        assert isinstance(minimum, int)
        if contract["workload_type"] == "scale_to_zero":
            assert minimum == 0, (environment, role)
        else:
            assert minimum >= 1, (environment, role)


@pytest.mark.parametrize(
    ("environment", "role", "config_key"),
    [
        ("dev", "api", "backend_fly_config"),
        ("dev", "frontend", "frontend_fly_config"),
        ("hml", "api", "backend_fly_config"),
        ("hml", "frontend", "frontend_fly_config"),
        ("prod", "api", "backend_fly_config"),
        ("prod", "frontend", "frontend_fly_config"),
    ],
)
def test_manifest_contract_matches_fly_config(
    environment: str, role: str, config_key: str
) -> None:
    """The declared contract must match the committed fly config, not hide it."""
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cfg = payload["environments"][environment]
    contract = cfg["workload_contracts"][role]
    content = (ROOT / cfg[config_key]).read_text(encoding="utf-8")

    declared = [
        int(line.split("=", 1)[1].strip())
        for line in content.splitlines()
        if line.strip().startswith("min_machines_running")
    ]
    assert declared, f"{cfg[config_key]} não declara min_machines_running"
    assert declared[0] == contract["min_machines_running"], (
        environment,
        role,
        cfg[config_key],
    )
    if contract["workload_type"] == "scale_to_zero":
        assert "auto_start_machines = true" in content, cfg[config_key]
