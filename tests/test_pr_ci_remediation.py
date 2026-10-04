from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "pr_ci_remediation.py"
spec = importlib.util.spec_from_file_location("pr_ci_remediation", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
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
        status="completed",
        conclusion=conclusion,
        run_attempt=attempt,
        html_url="https://github.com/example/repo/actions/runs/10",
        updated_at=updated,
    )


class RemediationClassificationTests(unittest.TestCase):
    def test_transient_allowlisted_is_rerun_candidate(self):
        state, action, reason, age = module.classify(make_run(conclusion="timed_out"), POLICY, now=NOW)
        self.assertEqual("CORRECAO_AUTOMATICA", state)
        self.assertEqual("rerun_failed_jobs", action)
        self.assertEqual("transient_allowlisted", reason)
        self.assertEqual(60, age)

    def test_deterministic_failure_requires_intervention(self):
        state, action, reason, _ = module.classify(make_run(conclusion="failure"), POLICY, now=NOW)
        self.assertEqual("INTERVENCAO_NECESSARIA", state)
        self.assertEqual("escalate", action)
        self.assertEqual("deterministic_or_unknown", reason)

    def test_high_risk_workflow_is_never_auto_remediated(self):
        state, action, reason, _ = module.classify(
            make_run(name="Security Deep Scan", conclusion="timed_out"), POLICY, now=NOW
        )
        self.assertEqual("INTERVENCAO_NECESSARIA", state)
        self.assertEqual("escalate", action)
        self.assertEqual("workflow_high_risk", reason)

    def test_attempt_limit_prevents_loop(self):
        state, action, reason, _ = module.classify(
            make_run(conclusion="timed_out", attempt=2), POLICY, now=NOW
        )
        self.assertEqual("INTERVENCAO_NECESSARIA", state)
        self.assertEqual("escalate", action)
        self.assertEqual("max_attempts_reached", reason)

    def test_latest_by_workflow_keeps_newest_execution(self):
        old = make_run(updated="2026-08-29T10:00:00Z")
        new = WorkflowRun(
            id=11,
            name=old.name,
            status="completed",
            conclusion="success",
            run_attempt=1,
            html_url="https://github.com/example/repo/actions/runs/11",
            updated_at="2026-08-29T11:30:00Z",
        )
        result = module.latest_by_workflow([old, new])
        self.assertEqual(1, len(result))
        self.assertEqual(11, result[0].id)

    def test_labels_mark_stalled_and_human_intervention(self):
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
        self.assertIn("ci:falhou", labels)
        self.assertIn("ci:intervencao-necessaria", labels)
        self.assertIn("ci:parado", labels)


if __name__ == "__main__":
    unittest.main()


class EventDrivenRemediationTests(unittest.TestCase):
    def test_pending_run_is_not_classified_as_recovered(self):
        run = WorkflowRun(
            id=12,
            name="CI Enterprise Fast",
            status="in_progress",
            conclusion="unknown",
            run_attempt=1,
            html_url="https://github.com/example/repo/actions/runs/12",
            updated_at="2026-08-29T11:30:00Z",
        )
        state, action, reason, _ = module.classify(run, POLICY, now=NOW)
        self.assertEqual("CI_PENDENTE", state)
        self.assertEqual("none", action)
        self.assertEqual("workflow_pending", reason)

    def test_select_prs_rejects_stale_workflow_event(self):
        original = module.fetch_pull_request
        try:
            module.fetch_pull_request = lambda repo, token, pr_number: module.PullRequest(
                number=81,
                title="PR",
                html_url="https://github.com/example/repo/pull/81",
                head_sha="a" * 40,
                head_ref="feature/test",
            )
            prs, reason = module.select_prs(
                "example/repo",
                "token",
                pr_number=81,
                expected_head_sha="b" * 40,
            )
        finally:
            module.fetch_pull_request = original
        self.assertEqual([], prs)
        self.assertEqual("stale_workflow_event", reason)

    def test_workflow_has_event_driven_primary_path_and_schedule_watchdog(self):
        raw = (Path(__file__).resolve().parents[1] / ".github/workflows/pr-ci-remediation.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_run:", raw)
        self.assertIn('"CI — ReqSys v2 Enterprise"', raw)
        self.assertIn('"CI Enterprise Fast"', raw)
        self.assertIn('"Pre-PR Readiness Gate"', raw)
        self.assertIn("EVENT_PR_NUMBER:", raw)
        self.assertIn("EVENT_HEAD_SHA:", raw)
        self.assertIn("schedule:", raw)


class TeamsEventNotificationContractTests(unittest.TestCase):
    def test_teams_notifier_consumes_automatic_triage_and_remediation_events(self):
        raw = (Path(__file__).resolve().parents[1] / ".github/workflows/teams-commit-notification.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_run:", raw)
        self.assertIn('"Ollama CI Triage"', raw)
        self.assertIn('"PR CI Remediation"', raw)
        self.assertIn("pr-ci-remediation-evidence-", raw)
        self.assertIn("ollama-ci-triage-", raw)
        self.assertIn("correção automática acionada", raw)
        self.assertIn("governed CI-driven merge PR #", raw)
