from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "scripts/configure_fecap_main_protection_risk3.py"
RUNNER = ROOT / "scripts/run_fecap_main_protection_local.py"


def test_fecap_risk3_action_is_fixed_and_secretless() -> None:
    raw = CONFIG.read_text(encoding="utf-8")
    assert 'ACTION_ID = "reqsys.fecap-main-protection.dev"' in raw
    assert 'SCOPE = "repo://ericson-j-santos/fecap-clipping-automation/branch/main"' in raw
    assert '"scripts/run_fecap_main_protection_local.py"' in raw
    assert "--token" not in raw
    assert "--secret" not in raw


def test_fecap_ruleset_runner_is_fixed_and_fail_closed() -> None:
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
    assert '"validated_source_not_parent_of_target"' in raw
    assert '"required_checks_not_green"' in raw
    assert '"branch_not_protected_after_write"' in raw
    assert '"ruleset_readback_mismatch"' in raw
    assert '"independent_readback": True' in raw
    assert '"secret_value_exposed": False' in raw


def test_fecap_runner_does_not_expose_generic_admin_surface() -> None:
    raw = RUNNER.read_text(encoding="utf-8")
    assert "--repository" not in raw
    assert "--branch" not in raw
    assert "--ruleset-name" not in raw
    assert "--required-check" not in raw
    assert "TARGET_REPOSITORY =" in raw
    assert "TARGET_BRANCH =" in raw
