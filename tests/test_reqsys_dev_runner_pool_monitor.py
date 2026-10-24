from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_reqsys_dev_runner_pool import audit

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["self-hosted", "Windows", "X64", "reqsys-dev", "reqsys-dev-base-v1"]


def policy() -> dict:
    return {
        "pool": "reqsys-dev-pc-pool-v1",
        "minimum_online_runners": 2,
        "monitor_profile": "base",
        "profiles": {"base": {"runner_labels": REQUIRED}},
    }


def probe(
    slot: int,
    runner_name: str | None,
    *,
    status: str = "completed",
    conclusion: str | None = "success",
    labels: list[str] | None = None,
) -> dict:
    return {
        "id": slot,
        "name": f"ReqSys DEV runner lease probe ({slot})",
        "status": status,
        "conclusion": conclusion,
        "runner_name": runner_name,
        "labels": labels or REQUIRED,
    }


def test_audit_passes_with_two_eligible_online_runners():
    result = audit(policy(), {"jobs": [probe(1, "one"), probe(2, "two")]})

    assert result["status"] == "passed"
    assert result["online_eligible_runners"] == 2
    assert result["monitored_profile"] == "base"
    assert result["findings"] == []
    assert result["mode"] == "report_only"
    assert result["mutated"] is False
    assert result["production_touched"] is False


def test_audit_reports_unassigned_and_label_drift_without_mutation():
    result = audit(
        policy(),
        {
            "jobs": [
                probe(1, "noteri"),
                probe(2, None, status="queued", conclusion=None, labels=REQUIRED[:-1]),
            ]
        },
    )

    assert result["status"] == "degraded"
    assert result["online_eligible_runners"] == 1
    assert {item["type"] for item in result["findings"]} == {
        "probe_unassigned",
        "probe_incomplete",
        "runner_labels_mismatch",
        "insufficient_online_runners",
    }
    assert result["deploy_performed"] is False
    assert result["production_touched"] is False


def test_audit_rejects_two_successful_leases_served_by_one_runner():
    result = audit(policy(), {"jobs": [probe(1, "one"), probe(2, "one")]})

    assert result["status"] == "degraded"
    assert result["online_eligible_runners"] == 1
    assert {item["type"] for item in result["findings"]} == {
        "probe_runner_reused",
        "insufficient_online_runners",
    }


def test_monitor_workflow_is_scheduled_read_only_and_evidence_backed():
    raw = (ROOT / ".github/workflows/self-hosted-runner-governance-guard.yml").read_text(encoding="utf-8")
    configured = json.loads((ROOT / "config/reqsys-dev-runner-pool.json").read_text(encoding="utf-8"))

    assert configured["minimum_online_runners"] == 2
    assert configured["monitor_profile"] == "base"
    assert 'cron: "*/30 * * * *"' in raw
    assert "actions: read" in raw
    assert "contents: read" in raw
    assert "issues: write" not in raw
    assert "ReqSys DEV runner lease probe" in raw
    assert "matrix:" in raw
    assert "slot: [1, 2]" in raw
    assert "permission-administration: read" not in raw
    assert "GH_TOKEN: ${{ github.token }}" in raw
    assert "/actions/runs/${GITHUB_RUN_ID}/jobs?filter=latest" in raw
    assert "GH_PAT_ACTIONS" not in raw
    assert "audit_reqsys_dev_runner_pool.py" in raw
    assert "Mode: `report_only`" in raw
    assert "Production touched: `false`" in raw
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in raw
