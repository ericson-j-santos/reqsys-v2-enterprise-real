import json
import tempfile
import unittest
from pathlib import Path

from scripts.enrich_self_hosted_runner_governance_state import (
    build_card,
    enrich_brief,
    enrich_runtime,
)


class SelfHostedRunnerGovernanceStateTests(unittest.TestCase):
    def test_not_in_use_is_preventive_p2(self):
        card = build_card({
            "status": "pass",
            "self_hosted_usages": [],
            "violations": [],
            "policy": {"self_hosted_allowed": False, "approved_workflows": []},
        })

        self.assertEqual("not-in-use", card["status"])
        self.assertEqual("P2", card["severity"])
        self.assertFalse(card["production_blocker"])
        self.assertTrue(card["human_approval_required"])

    def test_governed_usage_remains_report_only(self):
        card = build_card({
            "status": "pass",
            "self_hosted_usages": [".github/workflows/ci.yml:10: runs-on: self-hosted"],
            "violations": [],
            "policy": {
                "self_hosted_allowed": True,
                "approved_workflows": [".github/workflows/ci.yml"],
                "required_adr": "docs/adr/ADR-999.md",
            },
        })

        self.assertEqual("governed", card["status"])
        self.assertTrue(card["self_hosted_in_use"])
        self.assertEqual("report-only", card["mode"])
        self.assertFalse(card["production_blocker"])

    def test_violation_is_attention_without_changing_readiness(self):
        runtime = {"summary": {"production_ready": True}, "guardrails": []}
        brief = {"indicadores": {"readiness_percent": 99}}
        card = build_card({
            "status": "fail",
            "self_hosted_usages": [".github/workflows/ci.yml:10: runs-on: self-hosted"],
            "violations": ["Workflow not allowlisted"],
            "policy": {"self_hosted_allowed": False},
        })

        enriched_runtime = enrich_runtime(runtime, card)
        enriched_brief = enrich_brief(brief, card)

        self.assertEqual("attention", card["status"])
        self.assertEqual("P1", card["severity"])
        self.assertTrue(enriched_runtime["summary"]["production_ready"])
        self.assertEqual(99, enriched_brief["indicadores"]["readiness_percent"])
        self.assertEqual("yellow", enriched_brief["semaforo_executivo"]["self_hosted_runner_governance"])

    def test_enrichment_is_idempotent(self):
        card = build_card({"status": "pass", "self_hosted_usages": [], "violations": [], "policy": {}})
        first = enrich_runtime({}, card)
        second = enrich_runtime(first, card)

        marker = "self_hosted_runner_governance_report_only"
        self.assertEqual(1, second["guardrails"].count(marker))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
