from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/codex-worker-pool-handoff.yml"
POLICY = ROOT / ".github/self-hosted-runner-policy.json"


def test_worker_pool_handoff_is_manual_scoped_and_fail_closed() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    enqueue = raw.split("  enqueue:", maxsplit=1)[1].split(
        "  portable-contract-e2e:", maxsplit=1
    )[0]

    assert "workflow_dispatch:" in raw
    assert "push:" in raw
    assert "schedule:" not in raw
    assert "pull_request:" not in raw
    assert "issues:" not in raw
    assert "if: github.event_name == 'workflow_dispatch'" in enqueue
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in enqueue
    assert "ref: ${{ inputs.base_sha }}" in enqueue
    assert "pending_development_worker_pool_bridge.py" in enqueue
    assert "http://127.0.0.1:8097" in enqueue
    assert "replay_created" in enqueue
    assert "independent_readback" in enqueue
    assert "contract_mode" in enqueue
    assert "legacy_fallback" in enqueue
    assert "dispatch_mode" in enqueue
    assert "work_v1" in enqueue
    assert "work_id" in enqueue
    assert 'contract_version -ne "v1"' in enqueue
    assert "secrets." not in raw
    assert "merge" not in enqueue.lower().replace("merge/deploy: não", "")
    assert "deploy" not in enqueue.lower().replace("merge/deploy: não", "")


def test_worker_pool_handoff_requires_exact_identity_inputs() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    for name in ("issue_number", "request_id", "base_branch", "base_sha", "correlation_id"):
        assert f"{name}:" in raw
    assert '${{ inputs.request_id }}' in raw
    assert '${{ inputs.base_sha }}' in raw


def test_worker_pool_handoff_is_explicitly_allowlisted() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["self_hosted_allowed"] is True
    assert ".github/workflows/codex-worker-pool-handoff.yml" in policy["approved_workflows"]
    assert policy["required_adr"]
