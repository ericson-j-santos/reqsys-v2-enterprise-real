from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

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
    return json.loads(
        (ROOT / "config/reqsys-dev-runner-pool.json").read_text(encoding="utf-8")
    )


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


def test_runtime_profile_accepts_capabilities_without_hostname_or_runner_id(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    runtime = tmp_path / "runtime-dev"
    repo.mkdir()
    runtime.mkdir()
    monkeypatch.setattr(
        preflight,
        "_origin_repository",
        lambda _: "ericson-j-santos/reqsys-v2-enterprise-real",
    )

    result = preflight.validate(
        policy(),
        manifest(runtime),
        profile="runtime",
        repo_paths=[repo],
        os_name="nt",
        which=lambda _: "tool",
        docker_engine_probe=lambda: True,
    )

    assert result["status"] == "eligible"
    assert result["runner_instance_id"] == "reqsys-pc-a1b2c3d4"
    assert "hostname" not in result
    assert "runner_id" not in result
    assert result["docker_engine_valid"] is True


def test_runtime_profile_rejects_cli_without_live_docker_engine(tmp_path):
    runtime = tmp_path / "runtime-dev"
    runtime.mkdir()
    with pytest.raises(preflight.PreflightError, match="docker_engine_unavailable"):
        preflight.validate(
            policy(),
            manifest(runtime),
            profile="runtime",
            repo_paths=[],
            os_name="nt",
            which=lambda _: "tool",
            docker_engine_probe=lambda: False,
        )


def test_missing_manifest_path_is_not_treated_as_a_reparse_point(tmp_path):
    assert preflight._is_reparse(tmp_path / "missing-runner-pool.json") is False


def test_missing_manifest_is_reported_without_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_reqsys_dev_runner.py",
            "--manifest",
            str(tmp_path / "missing-runner-pool.json"),
        ],
    )
    assert preflight.main() == 1
    assert (
        json.loads(capsys.readouterr().out)["reason_code"] == "runner_manifest_invalid"
    )


def test_manifest_and_runtime_parent_reparse_points_are_detected(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "runner-pool.json").write_text("{}", encoding="utf-8")
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)

    assert preflight._has_reparse_component(linked / "runner-pool.json") is True


def test_docker_probe_rejects_remote_environment_without_contacting_daemon(
    monkeypatch,
):
    monkeypatch.setenv("DOCKER_HOST", "tcp://prod.example:2376")
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail(
            "remote Docker endpoint must not be probed"
        ),
    )
    assert preflight._docker_engine_available() is False


def test_docker_probe_rejects_remote_context_and_accepts_local_npipe(monkeypatch):
    for name in preflight.REMOTE_DOCKER_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)
    responses = iter(
        [
            SimpleNamespace(returncode=0, stdout="tcp://hml.example:2376\n"),
            SimpleNamespace(returncode=0, stdout="npipe:////./pipe/docker_engine\n"),
            SimpleNamespace(returncode=0, stdout="27.3.1\n"),
        ]
    )
    monkeypatch.setattr(
        preflight.subprocess, "run", lambda *args, **kwargs: next(responses)
    )
    assert preflight._docker_engine_available() is False
    assert preflight._docker_engine_available() is True


def test_base_profile_does_not_require_docker_or_ollama(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    runtime = tmp_path / "runtime-dev"
    repo.mkdir()
    runtime.mkdir()
    value = manifest(runtime, "base")
    monkeypatch.setattr(
        preflight,
        "_origin_repository",
        lambda _: "ericson-j-santos/reqsys-v2-enterprise-real",
    )

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
    assert result["requested_profile"] == "base"
    assert result["configured_profile"] == "base"


def test_runtime_manifest_satisfies_base_without_requiring_docker(tmp_path):
    runtime = tmp_path / "runtime-dev"
    runtime.mkdir()
    result = preflight.validate(
        policy(),
        manifest(runtime, "runtime"),
        profile="base",
        repo_paths=[],
        os_name="nt",
        which=lambda tool: tool if tool in {"git", "python"} else None,
        docker_engine_probe=lambda: pytest.fail(
            "base capability must not probe the Docker engine"
        ),
    )
    assert result["requested_profile"] == "base"
    assert result["configured_profile"] == "runtime"
    assert "docker_engine_valid" not in result


def test_base_manifest_cannot_satisfy_runtime_profile(tmp_path):
    runtime = tmp_path / "runtime-dev"
    runtime.mkdir()
    with pytest.raises(
        preflight.PreflightError, match="profile_capability_insufficient"
    ):
        preflight.validate(
            policy(),
            manifest(runtime, "base"),
            profile="runtime",
            repo_paths=[],
            os_name="nt",
            which=lambda _: "tool",
            docker_engine_probe=lambda: True,
        )


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
        preflight.validate(
            policy(),
            value,
            profile="runtime",
            repo_paths=[],
            os_name="nt",
            which=lambda _: "tool",
        )


def test_preflight_requires_tools_and_runtime_root(tmp_path):
    missing = manifest(tmp_path / "missing")
    with pytest.raises(preflight.PreflightError, match="required_tool_missing"):
        preflight.validate(
            policy(),
            missing,
            profile="runtime",
            repo_paths=[],
            os_name="nt",
            which=lambda _: None,
        )


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"profile": "base"}, "profile_capability_insufficient"),
        ({"capabilities": ["git", "python"]}, "capability_scope_invalid"),
        (
            {"runner_labels": ["self-hosted", "Windows", "X64", "reqsys-dev"]},
            "runner_labels_invalid",
        ),
    ],
)
def test_preflight_rejects_manifest_that_overclaims_or_underclaims_profile(
    tmp_path, change, reason
):
    runtime = tmp_path / "runtime-dev"
    runtime.mkdir()
    value = manifest(runtime)
    value.update(change)
    with pytest.raises(preflight.PreflightError, match=reason):
        preflight.validate(
            policy(),
            value,
            profile="runtime",
            repo_paths=[],
            os_name="nt",
            which=lambda _: "tool",
        )


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
        assert all(
            "pc24x7" not in line and "noteri" not in line for line in profile_runs_on
        )


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
        label for profile in profiles.values() for label in profile["runner_labels"]
    }


def test_repository_governance_enforces_portable_pool_contract():
    ok, result = validate_governance(
        ROOT, Path(".github/self-hosted-runner-policy.json")
    )
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


def test_preflight_action_prefers_existing_user_runtime_manifest_then_legacy_env():
    raw = (ROOT / ".github/actions/reqsys-dev-runner-preflight/action.yml").read_text(
        encoding="utf-8"
    )
    assert "$configuredManifest = $env:REQSYS_DEV_RUNNER_MANIFEST" in raw
    assert (
        "$userManifest = Join-Path $env:LOCALAPPDATA 'ReqSys\\runner-pool.json'" in raw
    )
    assert "@('base', 'runtime') -ccontains '${{ inputs.profile }}'" in raw
    assert "Test-Path -LiteralPath $userManifest -PathType Leaf" in raw
    assert "$manifestPath = $configuredManifest" in raw
    assert "--manifest $manifestPath" in raw


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
    recovery = (
        ROOT / ".github/workflows/noteri-desktop-watchdog-recovery.yml"
    ).read_text(encoding="utf-8")
    canary = recovery.split("  runner-pool-canary:", 1)[1].split("  runner-canary:", 1)[
        0
    ]
    gateway = (
        ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"
    ).read_text(encoding="utf-8")
    assert "REQSYS_DEV_RUNNER_POOL_PICKUP_PROVEN" in canary
    assert (
        "runs-on: [self-hosted, Windows, X64, reqsys-dev, reqsys-dev-base-v1]" in canary
    )
    assert "uses: ./.github/actions/reqsys-dev-runner-preflight" in canary
    assert "authorization_comment_id" in canary
    assert "expected_sha" in canary
    assert "runtime_mutated = $false" in canary
    assert "deploy_performed = $false" in canary
    assert "production_touched = $false" in canary
    assert "DESKTOP-PDQK954" not in canary
    assert "target='noteri-desktop-watchdog-recovery.yml'" in gateway
    assert "mode='runner-pool-canary'" in gateway
    assert '-f expected_sha="$EXPECTED_SHA"' in gateway
    assert '-f authorization_comment_id="$AUTHORIZED_COMMENT_ID"' in gateway


def test_noteri_onboarding_is_owner_bound_and_defers_remote_labels_without_restart_or_canary():
    recovery = (
        ROOT / ".github/workflows/noteri-desktop-watchdog-recovery.yml"
    ).read_text(encoding="utf-8")
    onboard = recovery.split("  runner-pool-onboard-noteri:", 1)[1].split(
        "  runner-pool-canary:", 1
    )[0]
    gateway = (
        ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"
    ).read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in onboard
    assert (
        "reqsys-dev-base-v1"
        not in onboard.split("Install and validate exact base profile", 1)[0]
    )
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
    guard = (
        ROOT / ".github/workflows/self-hosted-runner-governance-guard.yml"
    ).read_text(encoding="utf-8")
    reconcile = guard.split("  runner-pool-label-reconcile:", 1)[1]
    gateway = (
        ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"
    ).read_text(encoding="utf-8")
    assert "runs-on: ubuntu-latest" in reconcile
    assert "/reqsys run noteri-runner-pool-label-reconcile" in reconcile
    assert "onboarding_run_id" in reconcile
    assert "artifact_prefix}-${ONBOARDING_RUN_ID}" in reconcile
    assert "ONBOARDING_CONTRACT_CHANGED" in reconcile
    assert "'.github/workflows/noteri-desktop-watchdog-recovery.yml'" in reconcile
    assert "'scripts/reconcile_reqsys_dev_runner_labels.py'" in reconcile
    assert "DISPATCH_ACTOR_NOT_AUTHORIZED" in reconcile
    assert "github-actions\\[bot\\]" in reconcile
    assert "scripts/reconcile_reqsys_dev_runner_labels.py plan" in reconcile
    assert "scripts/reconcile_reqsys_dev_runner_labels.py verify" in reconcile
    assert "steps.runner-administration-token.outputs.token" in reconcile
    assert "permission-actions: read" in reconcile
    assert "permission-administration: write" in reconcile
    assert "secrets.GH_PAT_ACTIONS" not in reconcile
    assert "actions/runners/${runner_id}/labels" in reconcile
    assert "-RestartRunnerService" not in reconcile
    assert "runner-pool-canary" not in reconcile
    assert "environment=prod" not in reconcile
    assert "mode='runner-pool-label-reconcile-noteri'" in gateway
    assert "target='self-hosted-runner-governance-guard.yml'" in gateway
    assert '-f onboarding_run_id="$onboarding_run_id"' in gateway


def test_pc24x7_onboarding_is_capability_selected_owner_bound_and_dev_only():
    recovery = (
        ROOT / ".github/workflows/noteri-desktop-watchdog-recovery.yml"
    ).read_text(encoding="utf-8")
    onboard = recovery.split("  runner-pool-onboard-pc24x7:", 1)[1].split(
        "  runner-pool-onboard-pc24x7-runtime:", 1
    )[0]
    guard = (
        ROOT / ".github/workflows/self-hosted-runner-governance-guard.yml"
    ).read_text(encoding="utf-8")
    gateway = (
        ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"
    ).read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in onboard
    assert "DESKTOP-PDQK954" not in onboard
    assert "RUNNER_NAME -ne" not in onboard
    assert "/reqsys run pc24x7-runner-pool-onboard" in onboard
    assert "runner_instance_id = $env:RUNNER_INSTANCE_ID" in onboard
    assert "bootstrap_selector = 'pc24x7'" in onboard
    assert "stage-runner-onboard" in onboard
    assert "STAGE-REQSYS-DEV-RUNNER-ADMIN-ONBOARD" in onboard
    assert "--owner-comment-id" in onboard
    assert "admin_secret_supplied = $false" in onboard
    assert "install_reqsys_dev_runner.ps1" not in onboard
    assert "Start-Process" not in onboard
    assert "-ApplyGitHubLabels" not in onboard
    assert "labels_applied = $false" in onboard
    assert "service_restart_scheduled = $true" in onboard
    assert "canary_dispatched = $false" in onboard
    assert "automatic_retry_enabled = $false" in onboard
    assert "deploy_performed = $false" in onboard
    assert "production_touched = $false" in onboard
    assert "runner-pool-label-reconcile-pc24x7" in guard
    assert "--selector-label" in guard
    assert "mode='runner-pool-onboard-pc24x7'" in gateway
    assert "mode='runner-pool-label-reconcile-pc24x7'" in gateway


def test_pc24x7_runtime_onboarding_is_user_scoped_and_requires_live_engine():
    recovery = (
        ROOT / ".github/workflows/noteri-desktop-watchdog-recovery.yml"
    ).read_text(encoding="utf-8")
    onboard = recovery.split("  runner-pool-onboard-pc24x7-runtime:", 1)[1].split(
        "  runner-pool-canary:", 1
    )[0]
    guard = (
        ROOT / ".github/workflows/self-hosted-runner-governance-guard.yml"
    ).read_text(encoding="utf-8")
    gateway = (
        ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"
    ).read_text(encoding="utf-8")

    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in onboard
    assert "/reqsys run pc24x7-runner-pool-runtime-onboard" in onboard
    assert "onboard_reqsys_dev_runner.ps1" in onboard
    assert "install_reqsys_dev_runner.ps1" not in onboard
    assert "-Profile runtime" in onboard
    assert "Join-Path $env:LOCALAPPDATA 'ReqSys'" in onboard
    assert "LOCAL_RUNTIME_PARENT_REPARSE_REFUSED" in onboard
    assert "LOCAL_RUNTIME_ROOT_REPARSE_REFUSED" in onboard
    assert "LOCAL_RUNNER_MANIFEST_REPARSE_REFUSED" in onboard
    assert "CURRENT_RUNNER_REGISTRATION_INVALID" in onboard
    assert "$env:GITHUB_WORKSPACE" in onboard
    assert "$env:RUNNER_WORKSPACE" not in onboard
    assert "$runnerRoots.Count -ne 1" in onboard
    assert "runner_registration_valid = $true" in onboard
    assert "RUNNER_SERVICE_CARDINALITY_INVALID" not in onboard
    assert "Get-Service -Name 'actions.runner.*'" not in onboard
    assert "REMOTE_DOCKER_ENDPOINT_REFUSED" in onboard
    assert "LOCAL_DOCKER_ENDPOINT_REQUIRED" in onboard
    assert "docker_endpoint_class = 'local_npipe'" in onboard
    assert "DOCKER_ENGINE_UNAVAILABLE" in onboard
    assert "REQSYS_DEV_RUNNER_RUNTIME_PROFILE_CONFIGURED" in onboard
    assert "docker_engine_valid = $true" in onboard
    assert "runner_env_updated = $false" in onboard
    assert "service_restart_required = $false" in onboard
    assert "service_restart_scheduled = $false" in onboard
    assert "Restart-Service" not in onboard
    assert "labels_applied = $false" in onboard
    assert "automatic_retry_enabled = $false" in onboard
    assert "deploy_performed = $false" in onboard
    assert "production_touched = $false" in onboard
    assert "DISPATCH_ACTOR_NOT_AUTHORIZED" in onboard
    assert "Validate runtime through the shared manifest resolver" in onboard
    assert "runner-pool-label-reconcile-pc24x7-runtime" in guard
    assert '--profile "${{ steps.onboarding.outputs.profile }}"' in guard
    assert "mode='runner-pool-onboard-pc24x7-runtime'" in gateway
    assert "mode='runner-pool-label-reconcile-pc24x7-runtime'" in gateway
