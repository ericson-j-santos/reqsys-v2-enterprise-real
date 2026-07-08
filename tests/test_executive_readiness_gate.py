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

    def test_ready_for_production_when_required_evidence_is_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
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
            self.write_json(root, "artifacts/security-baseline-report/security-baseline-report.json", {"status": "passed", "critical_count": 0, "high_count": 0})
            self.write_json(root, "artifacts/runtime-executive-regression-alert/runtime-executive-regression-alert.json", {"status": "passed", "production_blocked": False, "violations_count": 0})
            self.write_json(root, "artifacts/runtime-executive-post-deploy-state/runtime-executive-post-deploy-state.json", {"status": "passed"})
            self.write_json(root, "artifacts/pr-evidence-gate/pr-evidence-gate.json", {"gate": {"status": "passed", "failures": []}})

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


if __name__ == "__main__":
    unittest.main()
