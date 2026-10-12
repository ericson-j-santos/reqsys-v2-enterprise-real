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


def test_local_protection_is_fail_closed_and_preserves_auto_merge() -> None:
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
    assert '"auto_merge_precheck_unknown"' in raw
    assert '"auto_merge_changed_during_protection"' in raw
    assert '"--method", "PATCH"' not in raw
    assert '"auto_merge_modified": False' in raw
    assert '"auto_merge_unchanged": True' in raw
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



def _load_worker_main_protection():
    import importlib.util

    spec = importlib.util.spec_from_file_location("worker_main_protection_test", RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _simulate_protection(monkeypatch, tmp_path, initial_auto_merge, *, check_green=True, drift=False):
    import json
    import sys
    from types import SimpleNamespace

    module = _load_worker_main_protection()
    state = {"protected": False, "auto_merge": initial_auto_merge, "writes": [], "repo_reads": 0}
    sha = "a" * 40
    compliant = {
        "required_status_checks": {"strict": True, "contexts": ["test"]},
        "enforce_admins": {"enabled": True},
        "required_pull_request_reviews": {},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
    }

    def fake_read(args, reason):
        route = next((arg for arg in args if isinstance(arg, str) and arg.startswith("repos/")), "")
        if route.endswith("/branches/main"):
            return {"protected": state["protected"], "commit": {"sha": sha}}
        if route.endswith("/branches/main/protection"):
            return compliant
        if route.endswith("/check-runs?per_page=100"):
            return {"check_runs": ([{"name": "test", "status": "completed", "conclusion": "success"}]
                                   if check_green else [])}
        if route == "repos/ericson-j-santos/engineering-worker-pool":
            state["repo_reads"] += 1
            observed = (not initial_auto_merge if drift and state["repo_reads"] > 1
                        else state["auto_merge"])
            return {"allow_auto_merge": observed}
        raise AssertionError("unexpected_read_" + route)

    def fake_write(args, *, stdin=None):
        if args[:2] == ["auth", "status"]:
            return SimpleNamespace(returncode=0)
        if "--method" in args and args[args.index("--method") + 1] == "PUT":
            assert any("branches/main/protection" in arg for arg in args)
            payload = json.loads(stdin)
            assert payload["required_status_checks"] == {"strict": True, "contexts": ["test"]}
            assert payload["enforce_admins"] is True
            assert payload["allow_force_pushes"] is False
            assert payload["allow_deletions"] is False
            assert payload["required_pull_request_reviews"] is not None
            state["writes"].append("branch_protection_only")
            state["protected"] = True
            return SimpleNamespace(returncode=0)
        raise AssertionError("unexpected_write_or_repo_patch")

    monkeypatch.setattr(module, "_gh_json", fake_read)
    monkeypatch.setattr(module, "_gh", fake_write)
    monkeypatch.setattr(module.socket, "gethostname", lambda: "DESKTOP-PDQK954")
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "protection.json"
    monkeypatch.setattr(sys, "argv", ["protection", "--output", str(output)])
    return module, state, output


def test_admin_protection_applies_without_automerging_and_replays(monkeypatch, tmp_path):
    import json
    import pytest

    for value in (False, True):
        with monkeypatch.context() as m:
            module, state, evidence_file = _simulate_protection(m, tmp_path, value)
            assert module.main() == 0
            evidence = json.loads(evidence_file.read_text(encoding="utf-8"))
            assert evidence["status"] == "PROTECTION_APPLIED"
            assert evidence["auto_merge_enabled"] is value
            assert evidence["auto_merge_modified"] is False
            assert evidence["auto_merge_unchanged"] is True
            assert state["auto_merge"] is value
            assert state["writes"] == ["branch_protection_only"]

            assert module.main() == 0
            replay = json.loads(evidence_file.read_text(encoding="utf-8"))
            assert replay["status"] == "ALREADY_COMPLIANT"
            assert replay["auto_merge_enabled"] is value
            assert replay["auto_merge_unchanged"] is True
            assert state["writes"] == ["branch_protection_only"]


def test_admin_protection_blocks_without_required_check(monkeypatch, tmp_path):
    import json

    module, state, evidence_file = _simulate_protection(
        monkeypatch, tmp_path, False, check_green=False
    )
    assert module.main() == 20
    evidence = json.loads(evidence_file.read_text(encoding="utf-8"))
    assert evidence["status"] == "BLOCKED"
    assert evidence["reason"] == "required_checks_not_green"
    assert state["writes"] == []


def test_admin_protection_detects_concurrent_auto_merge_change(monkeypatch, tmp_path):
    import json

    module, state, evidence_file = _simulate_protection(
        monkeypatch, tmp_path, False, drift=True
    )
    assert module.main() == 20
    evidence = json.loads(evidence_file.read_text(encoding="utf-8"))
    assert evidence["status"] == "BLOCKED"
    assert evidence["reason"] == "auto_merge_changed_during_protection"
    assert state["writes"] == ["branch_protection_only"]


def test_workflow_requires_protection_only_evidence():
    raw = BRANCH_WORKFLOW.read_text(encoding="utf-8")
    assert raw.count("AUTO_MERGE_MUTATION_DETECTED") == 2
    assert "AUTO_MERGE_NOT_ENABLED" not in raw
    assert raw.count("Aplicar somente proteção via Owner Risk3 Gateway") == 2
