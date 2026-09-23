import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/codex-worker-pool-smoke-dev.yml"
SCRIPT = ROOT / "scripts/codex_worker_pool_smoke_dev.py"
GATEWAY = ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"
POLICY = ROOT / ".github/self-hosted-runner-policy.json"
SPEC = ROOT / ".sdd/specs/codex-worker-pool.spec.json"


def test_smoke_workflow_is_fixed_to_pc24x7_dev_and_sha_bound() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in raw
    assert "schedule:" not in raw
    assert "pull_request:" not in raw
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert 'DESKTOP-PDQK954' in raw
    assert '--expected-sha "${{ github.sha }}"' in raw
    assert '--correlation-id "$env:CORRELATION_ID"' in raw
    assert "Reconciliar runtime DEV do Worker Pool" in raw
    assert "scripts/pc24x7_worker_pool_reconcile.py" in raw
    assert "RECONCILE-CODEX-WORKER-POOL-DEV" in raw
    assert "WORKER_POOL_RUNTIME_RECONCILED" in raw
    assert "Runtime DEV: reconciliado antes do smoke" in raw
    assert "Lane sintética: desabilitada" in raw
    assert "Produção tocada: não" in raw
    assert "Deploy executado: não" in raw


def test_smoke_script_disables_lane_and_proves_no_execution() -> None:
    raw = SCRIPT.read_text(encoding="utf-8")

    assert 'SMOKE_REPOSITORY = "ericson-j-santos/codex-worker-pool-smoke"' in raw
    assert '"enabled": False' in raw
    assert '"max_in_flight": 1' in raw
    assert 'f"smoke-{expected_sha[:12]}"' in raw
    assert 'if task.get("state") != "queued" or task.get("leased_by") is not None:' in raw
    assert '"replay_created": False' in raw
    assert '"independent_readback": True' in raw
    assert '"secrets_exposed": False' in raw
    assert '"production_touched": False' in raw
    assert '"deploy_executed": False' in raw
    assert '["git", "rev-parse", "HEAD"]' in raw
    assert "checkout_sha_mismatch" in raw
    assert "resolve_token_file" in raw
    assert "token_file_from_env" not in raw


def test_gateway_and_policy_allow_only_fixed_worker_pool_smoke() -> None:
    gateway = GATEWAY.read_text(encoding="utf-8")
    policy = json.loads(POLICY.read_text(encoding="utf-8"))

    assert "github.event.issue.number == 1705" in gateway
    assert "github.event.comment.user.login == 'ericson-j-santos'" in gateway
    assert "github.event.comment.body == '/reqsys run codex-worker-pool-smoke-dev'" in gateway
    assert "target='codex-worker-pool-smoke-dev.yml'" in gateway
    assert "steps.route.outputs.target == 'codex-worker-pool-smoke-dev.yml'" in gateway
    assert ".github/workflows/codex-worker-pool-smoke-dev.yml" in policy["approved_workflows"]


def test_sdd_registers_runtime_smoke_and_tests() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))

    assert 1914 in spec["issues"]
    assert ".github/workflows/codex-worker-pool-smoke-dev.yml" in spec["files"]
    assert "scripts/codex_worker_pool_smoke_dev.py" in spec["files"]
    assert "tests/test_codex_worker_pool_smoke_dev.py" in spec["sdd_gate"]["tests"]
