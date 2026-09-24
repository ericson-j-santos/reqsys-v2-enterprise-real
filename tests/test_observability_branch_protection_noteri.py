import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/branch-protection-audit.yml"
POLICY = ROOT / ".github/self-hosted-runner-policy.json"
CONFIG = ROOT / "scripts/configure_observability_main_protection_risk3.py"
RUNNER = ROOT / "scripts/run_observability_main_protection_local.py"


def test_apply_job_uses_noteri_session_launcher_and_risk3() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in raw
    assert 'TARGET_REPO: C:\\dev\\reqsys-v2-enterprise-real' in raw
    assert "chatgpt-operational-rules" in raw
    assert "session_launcher.py" in raw
    assert "SESSION_LAUNCH_OK" in raw
    assert "--sync-ref" in raw and '"origin/main"' in raw
    assert "owner_risk3_gateway.py" in raw
    assert "reqsys.observability-main-protection.dev" in raw
    assert "repo://ericson-j-santos/observability-platform/branch/main" in raw
    assert "ENABLE-OBSERVABILITY-MAIN-PROTECTION-ONCE" in raw
    assert "DISABLE-OBSERVABILITY-MAIN-PROTECTION-ONCE" in raw
    assert "Remover autorização Risk3 temporária" in raw
    assert "GITHUB_PAT" not in raw


def test_risk3_action_is_fixed_and_contains_no_secret_argument() -> None:
    raw = CONFIG.read_text(encoding="utf-8")
    assert 'ACTION_ID = "reqsys.observability-main-protection.dev"' in raw
    assert 'SCOPE = "repo://ericson-j-santos/observability-platform/branch/main"' in raw
    assert '"scripts/run_observability_main_protection_local.py"' in raw
    assert "--token" not in raw
    assert "--secret" not in raw


def test_local_protection_script_is_dynamic_fail_closed_and_sanitized() -> None:
    raw = RUNNER.read_text(encoding="utf-8")
    assert 'TARGET_REPOSITORY = "ericson-j-santos/observability-platform"' in raw
    assert 'TARGET_BRANCH = "main"' in raw
    assert 'REQUIRED_CHECKS = ("test", "E2E Platform Evidence Gate / validate-evidence")' in raw
    assert 'env.pop("GH_TOKEN", None)' in raw
    assert 'env.pop("GITHUB_TOKEN", None)' in raw
    assert '"github_local_auth_unavailable"' in raw
    assert '"required_checks_not_green"' in raw
    assert '"target_sha_changed_before_write"' in raw
    assert '"target_sha_changed_after_write"' in raw
    assert '"branch_protection_update_failed"' in raw
    assert '"PROTECTION_APPLIED"' in raw
    assert '"ALREADY_COMPLIANT"' in raw
    assert '"secret_value_exposed": False' in raw


def test_branch_protection_workflow_is_self_hosted_allowlisted() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["self_hosted_allowed"] is True
    assert ".github/workflows/branch-protection-audit.yml" in policy["approved_workflows"]
    assert policy["required_adr"] == "docs/adr/ADR-046-pc24x7-substituicao-flyio.md"
