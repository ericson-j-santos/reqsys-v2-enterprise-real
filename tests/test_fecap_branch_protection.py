from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRANCH_WORKFLOW = ROOT / ".github/workflows/branch-protection-audit.yml"
GATEWAY_WORKFLOW = ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"
CONFIG = ROOT / "scripts/configure_fecap_main_protection_risk3.py"
RUNNER = ROOT / "scripts/run_fecap_main_protection_local.py"


def test_gateway_exposes_exact_fecap_noteri_command() -> None:
    raw = GATEWAY_WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.comment.body == '/reqsys run protect-fecap-main-noteri'" in raw
    assert "'/reqsys run protect-fecap-main-noteri')" in raw
    assert "mode='apply-fecap-main-noteri'" in raw


def test_fecap_workflow_is_noteri_governed_and_fixed() -> None:
    raw = BRANCH_WORKFLOW.read_text(encoding="utf-8")
    assert "- apply-fecap-main-noteri" in raw
    assert "apply-fecap-main-noteri:" in raw
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in raw
    assert 'if ($env:COMPUTERNAME -ne "Noteri")' in raw
    assert '"--session-prefix", "fecap-main-protect-noteri"' in raw
    assert "reqsys.fecap-main-protection.dev" in raw
    assert "repo://ericson-j-santos/fecap-clipping-automation/branch/main" in raw


def test_fecap_risk3_action_is_fixed_and_secretless() -> None:
    raw = CONFIG.read_text(encoding="utf-8")
    assert 'ACTION_ID = "reqsys.fecap-main-protection.dev"' in raw
    assert 'SCOPE = "repo://ericson-j-santos/fecap-clipping-automation/branch/main"' in raw
    assert '"scripts/run_fecap_main_protection_local.py"' in raw
    assert "--token" not in raw
    assert "--secret" not in raw


def test_fecap_ruleset_runner_is_fail_closed() -> None:
    raw = RUNNER.read_text(encoding="utf-8")
    assert 'TARGET_REPOSITORY = "ericson-j-santos/fecap-clipping-automation"' in raw
    assert 'TARGET_BRANCH = "main"' in raw
    assert 'RULESET_NAME = "main-protection"' in raw
    assert 'EXPECTED_TARGET_SHA = "2b72e45012faeef84d1828faa97b7b8d4efd968f"' in raw
    assert 'VALIDATED_SOURCE_SHA = "c756b4faa948a9a23f3faf09e2e5cf748914a5fd"' in raw
    assert 'REQUIRED_CHECKS = ("tests",)' in raw
    assert 'env.pop("GH_TOKEN", None)' in raw
    assert 'env.pop("GITHUB_TOKEN", None)' in raw
    assert '"~DEFAULT_BRANCH"' in raw
    assert '{"type": "deletion"}' in raw
    assert '{"type": "non_fast_forward"}' in raw
    assert '{"type": "required_linear_history"}' in raw
    assert '"dismiss_stale_reviews_on_push": True' in raw
    assert '"strict_required_status_checks_policy": True' in raw
    assert '"bypass_actors": []' in raw
    assert '"target_sha_changed"' in raw
    assert '"required_checks_not_green"' in raw
    assert '"branch_not_protected_after_write"' in raw
    assert '"ruleset_readback_mismatch"' in raw
    assert '"independent_readback": True' in raw
    assert '"secret_value_exposed": False' in raw
    assert "--repository" not in raw
