from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "autonomous-delivery-cycle.yml"
LATEST_CONTRACT = ROOT / "docs" / "ops-dashboard" / "data" / "autonomous-delivery-cycle-latest.json"
NEXT_QUEUE_CONTRACT = ROOT / "docs" / "ops-dashboard" / "data" / "autonomous-delivery-cycle-next-increments.json"


def test_autonomous_delivery_cycle_workflow_has_required_guardrails() -> None:
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "cycle:auto-merge-approved" in content
    assert "merge-queue:eligible" in content
    assert "REQUIRED_WORKFLOWS" in content
    assert "merge_method: 'squash'" in content
    assert "sha: pr.head.sha" in content
    assert "post_merge_push_observation" in content
    assert "autonomous-delivery-cycle-report" in content


def test_autonomous_delivery_cycle_latest_contract_is_seeded() -> None:
    payload = json.loads(LATEST_CONTRACT.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "1.0.0"
    assert payload["required_label"] == "cycle:auto-merge-approved"
    assert payload["candidate_count"] == 0
    assert payload["merged_count"] == 0
    assert "requires_all_required_workflows_green" in payload["guardrails"]


def test_autonomous_delivery_next_increment_queue_is_report_only() -> None:
    payload = json.loads(NEXT_QUEUE_CONTRACT.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "1.0.0"
    assert payload["queue"] == []
    assert payload["source"] == "autonomous-delivery-cycle"
    assert "no_automatic_code_generation_from_queue" in payload["guardrails"]
