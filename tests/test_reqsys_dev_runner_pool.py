from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import validate_reqsys_dev_runner as preflight
from scripts.check_self_hosted_runner_governance import validate as validate_governance

ROOT = Path(__file__).resolve().parents[1]
PORTABLE = (
    ".github/workflows/codex-ollama-e2e-dev.yml",
    ".github/workflows/codex-worker-pool-handoff.yml",
    ".github/workflows/figma-github-e2e-dev.yml",
    ".github/workflows/noteri-study-mode-dev-reconcile.yml",
    ".github/workflows/ollama-ci-triage.yml",
    ".github/workflows/pc24x7-teams-token-bootstrap.yml",
    ".github/workflows/todo-global-hourly-cycle.yml",
)


def policy() -> dict:
    return json.loads((ROOT / "config/reqsys-dev-runner-pool.json").read_text(encoding="utf-8"))


def manifest(runtime_root: Path) -> dict:
    return {
        "schema_version": 1,
        "pool": "reqsys-dev-pc-pool-v1",
        "environment": "dev",
        "runner_instance_id": "reqsys-pc-a1b2c3d4",
        "allowed_environments": ["dev"],
        "runtime_root": str(runtime_root),
        "capabilities": ["git", "python", "docker", "reqsys-source", "dev-runtime"],
        "safeguards": {
            "hml_enabled": False,
            "stg_enabled": False,
            "production_enabled": False,
            "automatic_retry_enabled": False,
        },
    }


def test_runtime_profile_accepts_capabilities_without_hostname_or_runner_id(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    runtime = tmp_path / "runtime-dev"
    repo.mkdir()
    runtime.mkdir()
    monkeypatch.setattr(preflight, "_origin_repository", lambda _: "ericson-j-santos/reqsys-v2-enterprise-real")

    result = preflight.validate(
        policy(), manifest(runtime), profile="runtime", repo_paths=[repo], os_name="nt", which=lambda _: "tool"
    )

    assert result["status"] == "eligible"
    assert result["runner_instance_id"] == "reqsys-pc-a1b2c3d4"
    assert "hostname" not in result
    assert "runner_id" not in result


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"environment": "prod"}, "environment_must_be_dev"),
        ({"allowed_environments": ["dev", "hml"]}, "environment_scope_invalid"),
        ({"runner_instance_id": "DESKTOP-PDQK954"}, "runner_instance_id_invalid"),
        ({"safeguards": {"production_enabled": True}}, "safeguards_invalid"),
    ],
)
def test_preflight_fails_closed_for_scope_or_identity(tmp_path, change, reason):
    runtime = tmp_path / "runtime-dev"
    runtime.mkdir()
    value = manifest(runtime)
    value.update(change)
    with pytest.raises(preflight.PreflightError, match=reason):
        preflight.validate(policy(), value, profile="runtime", repo_paths=[], os_name="nt", which=lambda _: "tool")


def test_preflight_requires_tools_and_runtime_root(tmp_path):
    missing = manifest(tmp_path / "missing")
    with pytest.raises(preflight.PreflightError, match="required_tool_missing"):
        preflight.validate(policy(), missing, profile="runtime", repo_paths=[], os_name="nt", which=lambda _: None)


def test_portable_workflows_use_shared_pool_and_have_no_fixed_machine_identity():
    for relative in PORTABLE:
        raw = (ROOT / relative).read_text(encoding="utf-8")
        assert "reqsys-dev-pool-v1" in raw
        assert "./.github/actions/reqsys-dev-runner-preflight" in raw
        assert "DESKTOP-PDQK954" not in raw
        assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" not in raw


def test_repository_governance_enforces_portable_pool_contract():
    ok, result = validate_governance(ROOT, Path(".github/self-hosted-runner-policy.json"))
    assert ok, result["violations"]


def test_onboarding_does_not_register_or_reconfigure_github_runner():
    raw = (ROOT / "scripts/onboard_reqsys_dev_runner.ps1").read_text(encoding="utf-8")
    assert "config.cmd" not in raw
    assert "remove.cmd" not in raw
    assert "REQSYS_DEV_RUNNER_MANIFEST" in raw
    assert "reqsys-dev-pool-v1" not in raw  # labels come from the versioned policy
