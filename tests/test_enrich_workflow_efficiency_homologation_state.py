import json
import tempfile
import unittest
from pathlib import Path

from scripts.enrich_workflow_efficiency_homologation_state import (
    enrich_executive_brief,
    enrich_readiness,
    enrich_runtime_index,
    summarize,
)


class WorkflowEfficiencyHomologationStateTests(unittest.TestCase):
    def setUp(self):
        self.evidence = {
            "status": "passed",
            "decision": "HOMOLOGATED",
            "correlation_id": "123-456-1",
            "generated_at": "2026-07-10T00:00:00+00:00",
            "source": "ops-dashboard-static",
            "checks": {
                "html_sha256": "abc",
                "contract_sha256": "def",
            },
            "workflow_efficiency": {
                "score_percent": 93.2,
                "mode": "report-only",
                "link": "data/ci-workflow-efficiency-dashboard.json",
            },
            "errors": [],
        }

    def test_summarizes_homologated_evidence(self):
        card = summarize(self.evidence)
        self.assertTrue(card["homologated"])
        self.assertTrue(card["artifact_valid"])
        self.assertTrue(card["report_only"])
        self.assertFalse(card["production_blocker"])
        self.assertEqual(card["score_percent"], 93.2)

    def test_enriches_runtime_index_idempotently(self):
        card = summarize(self.evidence)
        first = enrich_runtime_index({}, card)
        second = enrich_runtime_index(first, card)

        self.assertEqual(first, second)
        self.assertIn("workflow_efficiency_homologation", second["cards"])
        self.assertTrue(second["summary"]["workflow_efficiency_homologated"])
        self.assertEqual(
            second["guardrails"].count("workflow_efficiency_homologation_report_only"),
            1,
        )

    def test_enriches_brief_without_overriding_production_state(self):
        card = summarize(self.evidence)
        brief = {"estado_producao": "ready", "semaforo_executivo": {"producao": "green"}}
        enriched = enrich_executive_brief(brief, card)

        self.assertEqual(enriched["estado_producao"], "ready")
        self.assertEqual(enriched["semaforo_executivo"]["producao"], "green")
        self.assertEqual(enriched["semaforo_executivo"]["workflow_efficiency_homologation"], "green")

    def test_readiness_domain_is_non_blocking(self):
        card = summarize(self.evidence)
        gate = {
            "executive_readiness": {
                "decision": "READY_FOR_PRODUCTION",
                "ready_for_production": True,
                "blockers": [],
            }
        }
        enriched = enrich_readiness(gate, card)
        domain = enriched["domains"]["workflow_efficiency_homologation"]

        self.assertFalse(domain["production_blocker"])
        self.assertTrue(domain["report_only"])
        self.assertEqual(enriched["executive_readiness"]["decision"], "READY_FOR_PRODUCTION")
        self.assertEqual(enriched["executive_readiness"]["blockers"], [])

    def test_failed_evidence_becomes_yellow_not_blocking(self):
        evidence = dict(self.evidence)
        evidence.update({"status": "failed", "decision": "BLOCKED", "errors": ["missing card"]})
        card = summarize(evidence)
        domain = enrich_readiness({}, card)["domains"]["workflow_efficiency_homologation"]

        self.assertFalse(card["homologated"])
        self.assertEqual(domain["state"], "yellow")
        self.assertFalse(domain["production_blocker"])


if __name__ == "__main__":
    unittest.main()
