from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/codex-worker-pool-handoff.yml"
POLICY = ROOT / ".github/self-hosted-runner-policy.json"


def sections() -> tuple[str, str, str, str]:
    raw = WORKFLOW.read_text(encoding="utf-8")
    enqueue = raw.split("  enqueue:", maxsplit=1)[1].split(
        "  hosted-dev-proof:", maxsplit=1
    )[0]
    hosted = raw.split("  hosted-dev-proof:", maxsplit=1)[1].split(
        "  portable-contract-e2e:", maxsplit=1
    )[0]
    portable = raw.split("  portable-contract-e2e:", maxsplit=1)[1]
    return raw, enqueue, hosted, portable


def test_worker_pool_handoff_preserves_legacy_default() -> None:
    raw, enqueue, hosted, _portable = sections()

    assert "workflow_dispatch:" in raw
    assert "push:" in raw
    assert "schedule:" not in raw
    assert "pull_request:" not in raw
    assert "issues:" not in raw
    assert 'default: "legacy_pc24x7"' in raw
    assert "inputs.execution_mode == 'legacy_pc24x7'" in enqueue
    assert "runs-on: [self-hosted, Windows, X64, reqsys-dev, reqsys-dev-pool-v1]" in enqueue
    assert "./.github/actions/reqsys-dev-runner-preflight" in enqueue
    assert "ref: ${{ inputs.base_sha }}" in enqueue
    assert "pending_development_worker_pool_bridge.py" in enqueue
    assert "http://127.0.0.1:8097" in enqueue
    assert "replay_created" in enqueue
    assert "independent_readback" in enqueue
    assert "work_v1" in enqueue
    assert "secrets." not in raw
    assert "merge" not in enqueue.lower().replace("merge/deploy: não", "")
    assert "deploy" not in enqueue.lower().replace("merge/deploy: não", "")
    assert "inputs.execution_mode == 'hosted_dev_proof'" in hosted


def test_hosted_proof_has_narrow_oidc_and_governed_execution() -> None:
    raw, enqueue, hosted, portable = sections()

    assert "runs-on: ubuntu-24.04" in hosted
    assert "id-token: write" in hosted
    assert "id-token: write" not in enqueue
    assert "id-token: write" not in portable
    assert "5d8de580fea571404607aa80c7bd7637b4652db6" in hosted
    assert "reqsys-handoff-v1" not in raw  # selected inside the bounded controller
    assert "owner_risk3_gateway.py" in hosted
    assert "--action-id reqsys.hosted.worker_pool.proof" in hosted
    assert "hosted_worker_pool_reqsys_proof.py" in hosted
    assert "validate_hosted_worker_pool_reqsys_proof.py" in hosted
    assert "ACTIONS_ID_TOKEN_REQUEST_URL" in hosted
    assert "Merge/deploy/produção: não" in hosted
    assert "Custo adicional: R$ 0,00" in hosted


def test_worker_pool_handoff_requires_exact_identity_inputs() -> None:
    raw, _enqueue, _hosted, _portable = sections()
    for name in (
        "issue_number", "request_id", "base_branch", "base_sha",
        "correlation_id", "execution_mode",
    ):
        assert f"{name}:" in raw
    assert '${{ inputs.request_id }}' in raw
    assert '${{ inputs.base_sha }}' in raw


def test_worker_pool_handoff_is_explicitly_allowlisted() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["self_hosted_allowed"] is True
    assert ".github/workflows/codex-worker-pool-handoff.yml" in policy["approved_workflows"]
    assert policy["required_adr"]
