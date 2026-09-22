import json
import tempfile
import unittest
from pathlib import Path

from scripts.executive_readiness_gate import build_gate


class ExecutiveReadinessGateTests(unittest.TestCase):
    def write_json(self, root: Path, relative: str, payload: dict) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def write_minimum_green_evidence(self, root: Path) -> None:
        self.write_json(
            root,
            "artifacts/runtime-validation-consolidator/runtime-validation-snapshot.json",
            {
                "overall_state": "green",
                "post_merge_ready": True,
                "public_runtime_ready": True,
                "production_ready": True,
                "blockers": [],
                "domains": {"public_smoke": {"state": "green", "score": 100, "available": True, "detail": "ok"}},
                "evidence_gate_consolidated": {"consolidated": True, "state": "green"},
            },
        )
        self.write_json(
            root,
            "docs/ops-dashboard/data/executive-brief.json",
            {"semaforo_executivo": {"merge_queue": "green", "auto_merge": "green", "seguranca": "green", "regressao_temporal": "green"}},
        )
        self.write_json(root, "artifacts/runtime-executive-regression-alert/runtime-executive-regression-alert.json", {"status": "passed", "production_blocked": False, "violations_count": 0})
        self.write_json(root, "artifacts/runtime-executive-post-deploy-state/runtime-executive-post-deploy-state.json", {"status": "passed"})
        self.write_json(root, "artifacts/pr-evidence-gate/pr-evidence-gate.json", {"gate": {"status": "passed", "failures": []}})

    def test_ready_for_production_when_required_evidence_is_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_minimum_green_evidence(root)
            self.write_json(root, "artifacts/security-baseline-report/security-baseline-report.json", {"status": "passed", "critical_count": 0, "high_count": 0})

            gate = build_gate("example/repo", "main", root, "cid-test")

            self.assertTrue(gate["executive_readiness"]["ready_for_production"])
            self.assertEqual(gate["executive_readiness"]["decision"], "READY_FOR_PRODUCTION")
            self.assertEqual(gate["executive_readiness"]["blockers"], [])
            self.assertGreaterEqual(gate["executive_readiness"]["score"], 90)

    def test_blocks_production_when_regression_alert_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_json(
                root,
                "artifacts/runtime-validation-consolidator/runtime-validation-snapshot.json",
                {
                    "overall_state": "green",
                    "post_merge_ready": True,
                    "public_runtime_ready": True,
                    "domains": {"public_smoke": {"state": "green", "score": 100, "available": True, "detail": "ok"}},
                    "evidence_gate_consolidated": {"consolidated": True, "state": "green"},
                },
            )
            self.write_json(root, "docs/ops-dashboard/data/executive-brief.json", {"semaforo_executivo": {"merge_queue": "green", "auto_merge": "green", "seguranca": "green"}})
            self.write_json(root, "artifacts/security-baseline-report/security-baseline-report.json", {"status": "passed", "critical_count": 0})
            self.write_json(root, "artifacts/runtime-executive-regression-alert/runtime-executive-regression-alert.json", {"status": "blocked", "production_blocked": True, "violations_count": 1})

            gate = build_gate("example/repo", "main", root, "cid-test")

            self.assertFalse(gate["executive_readiness"]["ready_for_production"])
            self.assertIn("regressao_temporal_red", gate["executive_readiness"]["blockers"])
            self.assertEqual(gate["domains"]["regressao_temporal"]["state"], "red")

    def test_security_executive_summary_has_precedence_over_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_minimum_green_evidence(root)
            self.write_json(root, "artifacts/security-baseline-report/security-baseline-report.json", {"status": "passed", "critical_count": 0, "high_count": 0})
            self.write_json(
                root,
                "artifacts/security-executive-summary/security-executive-summary.json",
                {
                    "kind": "security_executive_summary",
                    "overall": {
                        "state": "red",
                        "decision": "BLOCKED_SECURITY_CRITICAL",
                        "score": 0,
                        "risk_percent": 100,
                        "production_blocked": True,
                        "missing_scanners": [],
                    },
                    "totals": {"findings": 1, "severity": {"critical": 1, "high": 0, "medium": 0, "low": 0, "unknown": 0}},
                    "scanners": {},
                },
            )

            gate = build_gate("example/repo", "main", root, "cid-security")

            self.assertFalse(gate["executive_readiness"]["ready_for_production"])
            self.assertIn("seguranca_red", gate["executive_readiness"]["blockers"])
            self.assertEqual(gate["domains"]["seguranca"]["state"], "red")
            self.assertEqual(gate["domains"]["seguranca"]["score"], 0)
            self.assertIn("source=security_executive_summary", gate["domains"]["seguranca"]["detail"])
            self.assertTrue(gate["sources"]["security_executive_summary"]["available"])

    def test_security_executive_summary_backlog_keeps_security_yellow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_minimum_green_evidence(root)
            self.write_json(
                root,
                "docs/ops-dashboard/data/security-executive-summary.json",
                {
                    "kind": "security_executive_summary",
                    "overall": {
                        "state": "yellow",
                        "decision": "REVIEW_SECURITY_BACKLOG",
                        "score": 82,
                        "risk_percent": 18,
                        "production_blocked": False,
                        "missing_scanners": [],
                    },
                    "totals": {"findings": 1, "severity": {"critical": 0, "high": 1, "medium": 0, "low": 0, "unknown": 0}},
                    "scanners": {},
                },
            )

            gate = build_gate("example/repo", "main", root, "cid-security-yellow")

            self.assertEqual(gate["domains"]["seguranca"]["state"], "yellow")
            self.assertEqual(gate["domains"]["seguranca"]["score"], 82)
            self.assertNotIn("seguranca_red", gate["executive_readiness"]["blockers"])


if __name__ == "__main__":
    unittest.main()
