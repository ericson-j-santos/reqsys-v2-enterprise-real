from pathlib import Path

WORKFLOW = Path(".github/workflows/branch-protection-audit.yml")
GATEWAY = Path(".github/workflows/reqsys-authorized-actions-gateway.yml")
RUNNER = Path("scripts/run_observability_main_protection_local.py")


def test_protection_apply_is_fixed_and_fail_closed() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    runner = RUNNER.read_text(encoding="utf-8")
    assert "apply-observability-platform" in raw
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in raw
    assert "ericson-j-santos/observability-platform" in runner
    assert 'REQUIRED_CHECK = "test"' in runner
    assert '"target_sha_changed_before_write"' in runner
    assert '"target_sha_changed_after_write"' in runner
    assert '"required_check_not_green"' in runner
    assert '"branch_not_protected_after_write"' in runner
    assert '"protection_readback_mismatch"' in runner
    assert '"required_pull_request_reviews"' in runner
    assert '"enforce_admins": True' in runner
    assert '"required_approving_review_count": 0' in runner
    assert '"allow_force_pushes": False' in runner
    assert '"allow_deletions": False' in runner


def test_admin_auth_is_local_and_not_injected_as_secret() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    runner = RUNNER.read_text(encoding="utf-8")
    assert "GITHUB_PAT" not in raw
    assert 'env.pop("GH_TOKEN", None)' in runner
    assert 'env.pop("GITHUB_TOKEN", None)' in runner
    assert '"github_local_auth_unavailable"' in runner
    assert '"secret_value_exposed": False' in runner


def test_authorized_gateway_exposes_only_exact_command() -> None:
    raw = GATEWAY.read_text(encoding="utf-8")
    command = "/reqsys run protect-observability-platform-main"
    assert command in raw
    assert "target='branch-protection-audit.yml'" in raw
    assert "mode='apply-observability-platform'" in raw
    assert '-f mode="$TARGET_MODE"' in raw
