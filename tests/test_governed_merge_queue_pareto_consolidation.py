from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/governed-merge-queue.yml"
POLICY = ROOT / "governance/merge/current-sha-required-workflows.json"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_merge_queue_does_not_repeat_canonical_validation_jobs() -> None:
    text = _workflow_text()
    assert "\n  sdd-contract:" not in text
    assert "\n  isolated-validation:" not in text
    assert "needs: [resolve-context, temporary-integration, current-sha-stability]" in text
    assert "needs: resolve-context" in text
    assert "canonical_ci_same_sha: $stability_result" in text


def test_same_sha_policy_keeps_canonical_blocking_gates() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    required = set(policy["required_workflows"])
    assert {
        "Pre-PR Readiness Gate",
        "CI — ReqSys v2 Enterprise",
        "CI Enterprise Fast",
    } <= required


def test_negative_missing_canonical_gate_would_break_contract() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    required = set(policy["required_workflows"])
    required.remove("CI Enterprise Fast")
    assert not {
        "Pre-PR Readiness Gate",
        "CI — ReqSys v2 Enterprise",
        "CI Enterprise Fast",
    } <= required
