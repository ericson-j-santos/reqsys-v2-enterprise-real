from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "pr_ci_remediation.py"
spec = importlib.util.spec_from_file_location("pr_ci_remediation", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

WorkflowRun = module.WorkflowRun

POLICY = {
    "max_rerun_attempts": 2,
    "age_thresholds_minutes": {"stalled": 30, "priority": 120, "alert": 480, "critical": 1440},
    "transient_conclusions": ["cancelled", "timed_out", "stale"],
    "rerun_allowlist": ["CI Enterprise Fast"],
    "never_auto_remediate_keywords": ["security", "governance", "audit", "database"],
    "labels": {
        "failed": "ci:falhou",
        "handling": "ci:em-tratamento",
        "recovered": "ci:recuperado",
        "human": "ci:intervencao-necessaria",
        "transient": "ci:falha-transitoria",
        "stalled": "ci:parado",
    },
}
NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def make_run(*, name="CI Enterprise Fast", conclusion="failure", attempt=1, updated="2026-08-29T11:00:00Z"):
    return WorkflowRun(
        id=10,
        name=name,
        conclusion=conclusion,
        run_attempt=attempt,
        html_url="https://github.com/example/repo/actions/runs/10",
        updated_at=updated,
    )


def test_transient_allowlisted_is_rerun_candidate():
    state, action, reason, age = module.classify(make_run(conclusion="timed_out"), POLICY, now=NOW)
    assert state == "CORRECAO_AUTOMATICA"
    assert action == "rerun_failed_jobs"
    assert reason == "transient_allowlisted"
    assert age == 60


def test_deterministic_failure_requires_intervention():
    state, action, reason, _ = module.classify(make_run(conclusion="failure"), POLICY, now=NOW)
    assert state == "INTERVENCAO_NECESSARIA"
    assert action == "escalate"
    assert reason == "deterministic_or_unknown"


def test_high_risk_workflow_is_never_auto_remediated():
    state, action, reason, _ = module.classify(
        make_run(name="Security Deep Scan", conclusion="timed_out"), POLICY, now=NOW
    )
    assert state == "INTERVENCAO_NECESSARIA"
    assert action == "escalate"
    assert reason == "workflow_high_risk"


def test_attempt_limit_prevents_loop():
    state, action, reason, _ = module.classify(
        make_run(conclusion="timed_out", attempt=2), POLICY, now=NOW
    )
    assert state == "INTERVENCAO_NECESSARIA"
    assert action == "escalate"
    assert reason == "max_attempts_reached"


def test_latest_by_workflow_keeps_newest_execution():
    old = make_run(updated="2026-08-29T10:00:00Z")
    new = WorkflowRun(
        id=11,
        name=old.name,
        conclusion="success",
        run_attempt=1,
        html_url="https://github.com/example/repo/actions/runs/11",
        updated_at="2026-08-29T11:30:00Z",
    )
    result = module.latest_by_workflow([old, new])
    assert len(result) == 1
    assert result[0].id == 11


def test_labels_mark_stalled_and_human_intervention():
    decision = module.RemediationDecision(
        pr_number=1,
        pr_url="https://github.com/example/repo/pull/1",
        head_sha="abc",
        workflow_name="CI Enterprise Fast",
        run_id=10,
        run_url="https://github.com/example/repo/actions/runs/10",
        conclusion="failure",
        age_minutes=31,
        state="INTERVENCAO_NECESSARIA",
        action="escalate",
        reason="deterministic_or_unknown",
        rerun_executed=False,
    )
    labels = module.desired_labels([decision], POLICY)
    assert "ci:falhou" in labels
    assert "ci:intervencao-necessaria" in labels
    assert "ci:parado" in labels
