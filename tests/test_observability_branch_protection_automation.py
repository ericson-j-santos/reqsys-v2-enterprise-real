from pathlib import Path

WORKFLOW = Path(".github/workflows/branch-protection-audit.yml")
GATEWAY = Path(".github/workflows/reqsys-authorized-actions-gateway.yml")


def test_protection_apply_is_fixed_and_fail_closed() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "apply-observability-platform" in raw
    assert "ericson-j-santos/observability-platform" in raw
    assert "EXPECTED_TARGET_SHA: a13450360b85676f40932019119137d89313c58e" in raw
    assert "REQUIRED_CHECK: test" in raw
    assert "TARGET_SHA_CHANGED" in raw
    assert "REQUIRED_CHECK_NOT_GREEN" in raw
    assert '"contexts": ["test"]' in raw
    assert '"enforce_admins": True' in raw
    assert '"required_approving_review_count": 0' in raw
    assert '"allow_force_pushes": False' in raw
    assert '"allow_deletions": False' in raw
    assert "BRANCH_NOT_PROTECTED" in raw
    assert "REQUIRED_CHECK_MISSING" in raw
    assert "FORCE_PUSH_STILL_ALLOWED" in raw
    assert "BRANCH_DELETION_STILL_ALLOWED" in raw


def test_admin_token_is_secret_backed_and_not_echoed() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "GH_TOKEN: ${{ secrets.GITHUB_PAT }}" in raw
    assert "secret_value_exposed" in raw
    assert "echo $GH_TOKEN" not in raw
    assert "print(os.environ[\"GH_TOKEN\"])" not in raw


def test_authorized_gateway_exposes_only_exact_command() -> None:
    raw = GATEWAY.read_text(encoding="utf-8")
    command = "/reqsys run protect-observability-platform-main"
    assert command in raw
    assert "target='branch-protection-audit.yml'" in raw
    assert "mode='apply-observability-platform'" in raw
    assert '-f mode="$TARGET_MODE"' in raw
