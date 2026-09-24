from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/codex-worker-pool-handoff.yml"
SCRIPT = ROOT / "scripts/worker_pool_portable_contract_e2e.py"
REQUIREMENTS = ROOT / ".sdd/specs/codex-branch-first-worker-pool-bridge.requirements.md"
SPEC = ROOT / ".sdd/specs/codex-branch-first-worker-pool-bridge.spec.json"

WORKER_POOL_SHA = "0b4a5be12e49b45e3ff288dccacdd69fd87b57e0"
RULES_SHA = "5d1f603241dde37a597d2b7bdc5e07425db7b451"


def test_portable_e2e_workflow_is_github_hosted_sha_pinned_and_secretless() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    portable = raw.split("  portable-contract-e2e:", maxsplit=1)[1]

    assert "if: github.event_name == 'push'" in portable
    assert "runs-on: ubuntu-latest" in portable
    assert "self-hosted" not in portable
    assert "repository: ericson-j-santos/engineering-worker-pool" in portable
    assert f"ref: {WORKER_POOL_SHA}" in portable
    assert f"WORKER_POOL_SHA: {WORKER_POOL_SHA}" in portable
    assert f"RULES_SHA: {RULES_SHA}" in portable
    assert "permissions:\n  contents: read" in raw
    assert "secrets." not in raw
    assert "workflow_dispatch:" in raw
    assert "push:" in raw
    assert "timeout-minutes: 8" in portable
    assert "worker_pool_portable_contract_e2e.py" in portable
    assert "deploy" not in portable.lower().replace("deploy_executed", "").replace("deploy executado", "")


def test_portable_e2e_script_requires_work_v1_and_prevents_execution() -> None:
    raw = SCRIPT.read_text(encoding="utf-8")

    assert "allow_legacy_fallback=False" in raw
    assert "allow_work_fallback=False" in raw
    assert '"enabled": False' in raw
    assert '"max_in_flight": 1' in raw
    assert '"portable-e2e-invalid-token"' in raw
    assert '"worker_pool_http_401"' in raw
    assert '"dispatch_mode": "work_v1"' in raw
    assert '"physical_runtime_validated": False' in raw
    assert '"legacy_fallback_used": False' in raw
    assert "snapshot.get(\"workers\")" in raw
    assert 'task_readback.get("state") != "queued"' in raw
    assert 'task_readback.get("leased_by") is not None' in raw
    assert "subprocess.DEVNULL" in raw
    assert "secrets.token_urlsafe" in raw
    assert "lease_token" in raw


def test_portable_e2e_is_registered_as_issue_2020_gap_without_replacing_physical_gate() -> None:
    requirements = REQUIREMENTS.read_text(encoding="utf-8")
    spec = SPEC.read_text(encoding="utf-8")

    assert "E2E portátil" in requirements
    assert "não substitui" in requirements
    assert "PC24x7" in requirements
    assert ".github/workflows/codex-worker-pool-handoff.yml" in spec
    assert "worker-pool-portable-contract-e2e.yml" not in spec
    assert "worker_pool_portable_contract_e2e.py" in spec
    assert "test_worker_pool_portable_contract_e2e.py" in spec
    assert "2020" in spec
