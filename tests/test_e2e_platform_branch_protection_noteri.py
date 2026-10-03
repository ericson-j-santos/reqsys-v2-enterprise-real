import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/branch-protection-audit.yml"
GATEWAY = ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"
POLICY = ROOT / ".github/self-hosted-runner-policy.json"
CONFIG = ROOT / "scripts/configure_e2e_platform_main_protection_risk3.py"
RUNNER = ROOT / "scripts/run_e2e_platform_main_protection_local.py"


def test_e2e_platform_apply_job_is_fixed_governed_and_fail_closed() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    gateway = GATEWAY.read_text(encoding="utf-8")
    runner = RUNNER.read_text(encoding="utf-8")
    assert "apply-e2e-platform" in workflow
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in workflow
    assert "reqsys.e2e-platform-main-protection.dev" in workflow
    assert "repo://ericson-j-santos/e2e-platform/branch/main" in workflow
    assert "ENABLE-E2E-PLATFORM-MAIN-PROTECTION-ONCE" in workflow
    assert "DISABLE-E2E-PLATFORM-MAIN-PROTECTION-ONCE" in workflow
    assert "/reqsys run protect-e2e-platform-main" in gateway
    assert "mode='apply-e2e-platform'" in gateway
    assert 'TARGET_REPOSITORY = "ericson-j-santos/e2e-platform"' in runner
    assert 'REQUIRED_CHECKS = ("contract-self-test",)' in runner
    assert '"required_checks_not_green"' in runner
    assert '"target_sha_changed_before_write"' in runner
    assert '"target_sha_changed_after_write"' in runner
    assert '"protection_readback_mismatch"' in runner


def test_e2e_platform_risk3_action_is_exact_temporary_and_secretless() -> None:
    raw = CONFIG.read_text(encoding="utf-8")
    assert 'ACTION_ID = "reqsys.e2e-platform-main-protection.dev"' in raw
    assert 'SCOPE = "repo://ericson-j-santos/e2e-platform/branch/main"' in raw
    assert '"scripts/run_e2e_platform_main_protection_local.py"' in raw
    assert "ENABLE-E2E-PLATFORM-MAIN-PROTECTION-ONCE" in raw
    assert "DISABLE-E2E-PLATFORM-MAIN-PROTECTION-ONCE" in raw
    assert "--token" not in raw
    assert "--secret" not in raw


def test_e2e_platform_local_auth_is_sanitized_and_workflow_allowlisted() -> None:
    runner = RUNNER.read_text(encoding="utf-8")
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert 'env.pop("GH_TOKEN", None)' in runner
    assert 'env.pop("GITHUB_TOKEN", None)' in runner
    assert '"secret_value_exposed": False' in runner
    assert policy["self_hosted_allowed"] is True
    assert ".github/workflows/branch-protection-audit.yml" in policy["approved_workflows"]
