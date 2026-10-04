from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRANCH_WORKFLOW = ROOT / ".github/workflows/branch-protection-audit.yml"
GATEWAY_WORKFLOW = ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"
CONFIG = ROOT / "scripts/configure_engineering_worker_pool_main_protection_risk3.py"
RUNNER = ROOT / "scripts/run_engineering_worker_pool_main_protection_local.py"


def test_gateway_exposes_exact_worker_pool_protection_command() -> None:
    raw = GATEWAY_WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.comment.body == '/reqsys run protect-engineering-worker-pool-main'" in raw
    assert "'/reqsys run protect-engineering-worker-pool-main')" in raw
    assert "mode='apply-engineering-worker-pool'" in raw


def test_branch_protection_job_is_pc24x7_governed() -> None:
    raw = BRANCH_WORKFLOW.read_text(encoding="utf-8")
    assert "- apply-engineering-worker-pool" in raw
    assert "apply-engineering-worker-pool:" in raw
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert "DESKTOP-PDQK954" in raw
    assert "session_launcher.py" in raw
    assert "SESSION_LAUNCH_OK" in raw
    assert "owner_risk3_gateway.py" in raw
    assert "reqsys.engineering-worker-pool-main-protection.dev" in raw
    assert "repo://ericson-j-santos/engineering-worker-pool/branch/main" in raw
    assert "ENABLE-ENGINEERING-WORKER-POOL-MAIN-PROTECTION-ONCE" in raw
    assert "DISABLE-ENGINEERING-WORKER-POOL-MAIN-PROTECTION-ONCE" in raw


def test_risk3_action_is_fixed_and_secretless() -> None:
    raw = CONFIG.read_text(encoding="utf-8")
    assert 'ACTION_ID = "reqsys.engineering-worker-pool-main-protection.dev"' in raw
    assert 'SCOPE = "repo://ericson-j-santos/engineering-worker-pool/branch/main"' in raw
    assert '"scripts/run_engineering_worker_pool_main_protection_local.py"' in raw
    assert "--token" not in raw
    assert "--secret" not in raw


def test_local_protection_is_fail_closed_and_enables_auto_merge() -> None:
    raw = RUNNER.read_text(encoding="utf-8")
    assert 'TARGET_REPOSITORY = "ericson-j-santos/engineering-worker-pool"' in raw
    assert 'TARGET_BRANCH = "main"' in raw
    assert 'REQUIRED_CHECKS = ("test",)' in raw
    assert 'env.pop("GH_TOKEN", None)' in raw
    assert 'env.pop("GITHUB_TOKEN", None)' in raw
    assert '"required_checks_not_green"' in raw
    assert '"target_sha_changed_before_write"' in raw
    assert '"target_sha_changed_after_write"' in raw
    assert '"branch_protection_update_failed"' in raw
    assert '"auto_merge_update_failed"' in raw
    assert '{"allow_auto_merge": True}' in raw
    assert '"auto_merge_readback_mismatch"' in raw
    assert '"PROTECTION_APPLIED"' in raw
    assert '"ALREADY_COMPLIANT"' in raw
    assert '"independent_readback": True' in raw
    assert '"secret_value_exposed": False' in raw

def test_gateway_exposes_exact_worker_pool_noteri_fallback_command() -> None:
    raw = GATEWAY_WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.comment.body == '/reqsys run protect-engineering-worker-pool-main-noteri'" in raw
    assert "'/reqsys run protect-engineering-worker-pool-main-noteri')" in raw
    assert "mode='apply-engineering-worker-pool-noteri'" in raw


def test_branch_protection_has_governed_noteri_fallback_without_removing_pc24x7() -> None:
    raw = BRANCH_WORKFLOW.read_text(encoding="utf-8")
    assert "- apply-engineering-worker-pool" in raw
    assert "- apply-engineering-worker-pool-noteri" in raw
    assert "apply-engineering-worker-pool:" in raw
    assert "apply-engineering-worker-pool-noteri:" in raw
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in raw
    assert 'if ($env:COMPUTERNAME -ne "DESKTOP-PDQK954")' in raw
    assert 'if ($env:COMPUTERNAME -ne "Noteri")' in raw
    assert '"--session-prefix", "worker-pool-protect-noteri"' in raw
    assert "Checkout ReqSys exact workflow SHA" in raw
    assert "TARGET_REPO: ${{ github.workspace }}" in raw
    assert "persist-credentials: false" in raw
    assert "881d9ca2f8e77025edb7298b22981109c567a730" in raw
    noteri_section = raw.split("apply-engineering-worker-pool-noteri:", maxsplit=1)[1]
    assert r"TARGET_REPO: C:\\dev\\reqsys-v2-enterprise-real" not in noteri_section
    assert "reqsys.engineering-worker-pool-main-protection.dev" in raw
    assert "repo://ericson-j-santos/engineering-worker-pool/branch/main" in raw

