from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import validate_reqsys_dev_runner as preflight
from scripts.check_self_hosted_runner_governance import validate as validate_governance

ROOT = Path(__file__).resolve().parents[1]
PORTABLE = {
    ".github/workflows/codex-ollama-e2e-dev.yml": "ollama",
    ".github/workflows/codex-worker-pool-handoff.yml": "base",
    ".github/workflows/figma-github-e2e-dev.yml": "base",
    ".github/workflows/noteri-desktop-watchdog-recovery.yml": "base",
    ".github/workflows/noteri-study-mode-dev-reconcile.yml": "runtime",
    ".github/workflows/ollama-ci-triage.yml": "ollama",
    ".github/workflows/pc24x7-teams-token-bootstrap.yml": "runtime",
    ".github/workflows/todo-global-hourly-cycle.yml": "runtime",
}

PROFILE_LABELS = {
    "base": "reqsys-dev-base-v1",
    "runtime": "reqsys-dev-runtime-v1",
    "ollama": "reqsys-dev-ollama-v1",
}


def policy() -> dict:
    return json.loads((ROOT / "config/reqsys-dev-runner-pool.json").read_text(encoding="utf-8"))


def manifest(runtime_root: Path, profile: str = "runtime") -> dict:
    selected = policy()["profiles"][profile]
    return {
        "schema_version": 1,
        "pool": "reqsys-dev-pc-pool-v1",
        "profile": profile,
        "environment": "dev",
        "runner_instance_id": "reqsys-pc-a1b2c3d4",
        "allowed_environments": ["dev"],
        "runtime_root": str(runtime_root),
        "capabilities": selected["capabilities"],
        "runner_labels": selected["runner_labels"],
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


def test_base_profile_does_not_require_docker_or_ollama(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    runtime = tmp_path / "runtime-dev"
    repo.mkdir()
    runtime.mkdir()
    value = manifest(runtime, "base")
    monkeypatch.setattr(preflight, "_origin_repository", lambda _: "ericson-j-santos/reqsys-v2-enterprise-real")

    result = preflight.validate(
        policy(),
        value,
        profile="base",
        repo_paths=[repo],
        os_name="nt",
        which=lambda tool: tool if tool in {"git", "python"} else None,
    )

    assert result["status"] == "eligible"
    assert result["profile"] == "base"


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


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"profile": "base"}, "profile_scope_invalid"),
        ({"capabilities": ["git", "python"]}, "capability_scope_invalid"),
        ({"runner_labels": ["self-hosted", "Windows", "X64", "reqsys-dev"]}, "runner_labels_invalid"),
    ],
)
def test_preflight_rejects_manifest_that_overclaims_or_underclaims_profile(tmp_path, change, reason):
    runtime = tmp_path / "runtime-dev"
    runtime.mkdir()
    value = manifest(runtime)
    value.update(change)
    with pytest.raises(preflight.PreflightError, match=reason):
        preflight.validate(policy(), value, profile="runtime", repo_paths=[], os_name="nt", which=lambda _: "tool")


def test_portable_workflows_use_profile_pool_and_have_no_fixed_machine_identity():
    for relative, profile in PORTABLE.items():
        raw = (ROOT / relative).read_text(encoding="utf-8")
        profile_runs_on = [
            line
            for line in raw.splitlines()
            if line.strip().startswith("runs-on:") and PROFILE_LABELS[profile] in line
        ]
        assert profile_runs_on
        for incompatible in set(PROFILE_LABELS.values()) - {PROFILE_LABELS[profile]}:
            assert all(incompatible not in line for line in profile_runs_on)
        assert "./.github/actions/reqsys-dev-runner-preflight" in raw
        assert all("DESKTOP-PDQK954" not in line for line in profile_runs_on)
        assert all("pc24x7" not in line and "noteri" not in line for line in profile_runs_on)


def test_profile_labels_are_cumulative_without_cross_profile_pickup():
    profiles = policy()["profiles"]
    assert profiles["base"]["runner_labels"][-1:] == [PROFILE_LABELS["base"]]
    assert profiles["runtime"]["runner_labels"][-2:] == [
        PROFILE_LABELS["base"],
        PROFILE_LABELS["runtime"],
    ]
    assert profiles["ollama"]["runner_labels"][-3:] == [
        PROFILE_LABELS["base"],
        PROFILE_LABELS["runtime"],
        PROFILE_LABELS["ollama"],
    ]
    assert "reqsys-dev-pool-v1" not in {
        label
        for profile in profiles.values()
        for label in profile["runner_labels"]
    }


def test_repository_governance_enforces_portable_pool_contract():
    ok, result = validate_governance(ROOT, Path(".github/self-hosted-runner-policy.json"))
    assert ok, result["violations"]


def test_onboarding_does_not_register_or_reconfigure_github_runner():
    raw = (ROOT / "scripts/onboard_reqsys_dev_runner.ps1").read_text(encoding="utf-8")
    assert "config.cmd" not in raw
    assert "remove.cmd" not in raw
    assert "REQSYS_DEV_RUNNER_MANIFEST" in raw
    assert "$selected.runner_labels" in raw
    assert "profile = $Profile" in raw
    assert "runner_labels = @($runnerLabels)" in raw
    assert "System.Text.UTF8Encoding($false)" in raw
    assert "reqsys-dev-base-v1" not in raw  # labels come from the versioned policy


def test_installer_configures_runner_env_and_requires_explicit_label_confirmation():
    raw = (ROOT / "scripts/install_reqsys_dev_runner.ps1").read_text(encoding="utf-8")
    assert "ADMINISTRATOR_REQUIRED" in raw
    assert "REQSYS_DEV_RUNNER_MANIFEST=" in raw
    assert "System.Text.UTF8Encoding($false)" in raw
    assert "APPLY-REQSYS-DEV-RUNNER-LABELS" in raw
    assert "GITHUB_LABEL_CONFIRMATION_REQUIRED" in raw
    assert "RUNNER_SERVICE_NAME_REQUIRED_OR_AMBIGUOUS" in raw
    assert "actions.runner.*" in raw
    assert "SetEnvironmentVariable" not in raw
    assert "DESKTOP-PDQK954" not in raw
    assert "automatic_retry_enabled = $false" in raw
    assert "production_touched = $false" in raw
    assert "[string]$Confirm" not in raw
    assert "[string]$LabelConfirmation" in raw


def test_pool_canary_is_owner_and_sha_bound_without_runtime_mutation():
    recovery = (ROOT / ".github/workflows/noteri-desktop-watchdog-recovery.yml").read_text(encoding="utf-8")
    canary = recovery.split("  runner-pool-canary:", 1)[1].split("  runner-canary:", 1)[0]
    gateway = (ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml").read_text(encoding="utf-8")
    assert "REQSYS_DEV_RUNNER_POOL_PICKUP_PROVEN" in canary
    assert "runs-on: [self-hosted, Windows, X64, reqsys-dev, reqsys-dev-base-v1]" in canary
    assert "uses: ./.github/actions/reqsys-dev-runner-preflight" in canary
    assert "authorization_comment_id" in canary
    assert "expected_sha" in canary
    assert "runtime_mutated = $false" in canary
    assert "deploy_performed = $false" in canary
    assert "production_touched = $false" in canary
    assert "DESKTOP-PDQK954" not in canary
    assert "target='noteri-desktop-watchdog-recovery.yml'" in gateway
    assert "mode='runner-pool-canary'" in gateway
    assert "-f expected_sha=\"$EXPECTED_SHA\"" in gateway
    assert "-f authorization_comment_id=\"$AUTHORIZED_COMMENT_ID\"" in gateway


def test_noteri_onboarding_is_owner_bound_and_defers_remote_labels_without_restart_or_canary():
    recovery = (ROOT / ".github/workflows/noteri-desktop-watchdog-recovery.yml").read_text(encoding="utf-8")
    onboard = recovery.split("  runner-pool-onboard-noteri:", 1)[1].split("  runner-pool-canary:", 1)[0]
    gateway = (ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml").read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in onboard
    assert "reqsys-dev-base-v1" not in onboard.split("Install and validate exact base profile", 1)[0]
    assert "/reqsys run noteri-runner-pool-onboard" in onboard
    assert "authorization_comment_id" in onboard
    assert "expected_sha" in onboard
    assert "install_reqsys_dev_runner.ps1" in onboard
    assert "-Profile base" in onboard
    assert "-ApplyGitHubLabels" not in onboard
    assert "-LabelConfirmation" not in onboard
    assert "secrets." not in onboard
    assert "labels_applied = $false" in onboard
    assert "label_reconciliation_required = $true" in onboard
    assert "-RestartRunnerService" not in onboard
    assert "canary_dispatched = $false" in onboard
    assert "automatic_retry_enabled = $false" in onboard
    assert "deploy_performed = $false" in onboard
    assert "production_touched = $false" in onboard
    assert "mode='runner-pool-onboard-noteri'" in gateway


def test_noteri_label_reconciliation_is_hosted_evidence_bound_and_dev_only():
    guard = (ROOT / ".github/workflows/self-hosted-runner-governance-guard.yml").read_text(encoding="utf-8")
    reconcile = guard.split("  runner-pool-label-reconcile-noteri:", 1)[1]
    gateway = (ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml").read_text(encoding="utf-8")
    assert "runs-on: ubuntu-latest" in reconcile
    assert "/reqsys run noteri-runner-pool-label-reconcile" in reconcile
    assert "onboarding_run_id" in reconcile
    assert "reqsys-dev-runner-pool-onboard-${ONBOARDING_RUN_ID}" in reconcile
    assert "ONBOARDING_CONTRACT_CHANGED" in reconcile
    assert "scripts/reconcile_reqsys_dev_runner_labels.py plan" in reconcile
    assert "scripts/reconcile_reqsys_dev_runner_labels.py verify" in reconcile
    assert "secrets.GH_PAT_ACTIONS" in reconcile
    assert "actions/runners/${runner_id}/labels" in reconcile
    assert "-RestartRunnerService" not in reconcile
    assert "runner-pool-canary" not in reconcile
    assert "environment=prod" not in reconcile
    assert "mode='runner-pool-label-reconcile-noteri'" in gateway
    assert "target='self-hosted-runner-governance-guard.yml'" in gateway
    assert '-f onboarding_run_id="$onboarding_run_id"' in gateway
