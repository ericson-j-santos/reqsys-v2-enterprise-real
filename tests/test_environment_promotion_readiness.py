import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build_environment_promotion_readiness import build


class EnvironmentPromotionReadinessTests(unittest.TestCase):
    def write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_blocks_when_environment_evidence_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_json(root / "artifacts/executive-readiness-gate/executive-readiness-gate.json", {"executive_readiness": {"ready_for_production": True, "decision": "READY_FOR_PRODUCTION", "score": 98, "blockers": []}})
            with patch("scripts.build_environment_promotion_readiness.DEFAULT_INPUTS", {"executive_readiness": root / "artifacts/executive-readiness-gate/executive-readiness-gate.json", "runtime_index": root / "docs/ops-dashboard/data/runtime-executive-index.json"}), patch("scripts.build_environment_promotion_readiness.evidence_candidates", lambda env: [root / f"artifacts/fly-homologation/evidence-{env}.json"]):
                payload = build("example/repo")

            self.assertFalse(payload["ready_for_prod_promotion"])
            self.assertEqual(payload["decision"], "BLOCKED_FOR_PROD_PROMOTION")
            self.assertIn("env_dev_evidence_missing", payload["production_blockers"])
            self.assertEqual(payload["coverage"]["coverage_percent"], 0)

    def test_ready_when_executive_and_all_environments_are_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_json(root / "artifacts/executive-readiness-gate/executive-readiness-gate.json", {"executive_readiness": {"ready_for_production": True, "decision": "READY_FOR_PRODUCTION", "score": 99, "blockers": []}})
            for env in ("dev", "stg", "prod"):
                self.write_json(root / f"artifacts/fly-homologation/evidence-{env}.json", {"ok": True, "environment": env, "base_url": f"https://{env}.example.test", "probes": [{"ok": True}], "blocking_issues": [], "expected_sha": "abcdef123456", "observed_sha": "abcdef123456"})

            with patch("scripts.build_environment_promotion_readiness.DEFAULT_INPUTS", {"executive_readiness": root / "artifacts/executive-readiness-gate/executive-readiness-gate.json", "runtime_index": root / "docs/ops-dashboard/data/runtime-executive-index.json"}), patch("scripts.build_environment_promotion_readiness.evidence_candidates", lambda env: [root / f"artifacts/fly-homologation/evidence-{env}.json"]):
                payload = build("example/repo", "abcdef123456")

            self.assertTrue(payload["ready_for_prod_promotion"])
            self.assertEqual(payload["decision"], "READY_FOR_PROD_PROMOTION")
            self.assertEqual(payload["production_blockers"], [])
            self.assertEqual(payload["coverage"]["coverage_percent"], 100)


if __name__ == "__main__":
    unittest.main()
