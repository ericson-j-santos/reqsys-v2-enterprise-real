import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_executive_promotion_advisor_homologation_history import build
from scripts.homologate_executive_promotion_advisor_artifact import homologate


class AdvisorPostArtifactHomologationTests(unittest.TestCase):
    def make_root(self, card=None):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "data").mkdir()
        (root / "index.html").write_text(
            '<html><section id="executive-promotion-advisor-card"></section></html>',
            encoding="utf-8",
        )
        payload = {"cards": {"executive_promotion_advisor": card or {
            "decision": "REVIEW",
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
        }}}
        (root / "data" / "runtime-executive-index.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        return tmp, root

    def test_artifact_homologated_when_public_not_configured(self):
        tmp, root = self.make_root()
        self.addCleanup(tmp.cleanup)
        result = homologate(root)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["decision"], "ARTIFACT_HOMOLOGATED_PUBLIC_PENDING")
        self.assertFalse(result["production_blocker"])
        self.assertTrue(result["human_approval_required"])

    def test_invalid_guardrail_blocks_artifact_homologation(self):
        tmp, root = self.make_root({
            "decision": "READY",
            "mode": "blocking",
            "production_blocker": True,
            "human_approval_required": False,
        })
        self.addCleanup(tmp.cleanup)
        result = homologate(root)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("advisor_not_report_only", result["errors"])

    def test_history_is_idempotent_and_non_blocking(self):
        evidence = {
            "generated_at": "2026-07-11T00:00:00+00:00",
            "decision": "HOMOLOGATED",
            "status": "passed",
            "artifact": {"status": "passed"},
            "public_url": {"observed": True, "status": "passed"},
            "errors": [],
        }
        history = build({}, evidence)
        history = build(history, evidence)
        self.assertEqual(history["summary"]["sample_count"], 1)
        self.assertEqual(history["summary"]["stable_streak"], 1)
        self.assertFalse(history["summary"]["production_blocker"])

    def test_gate_review_requires_full_policy(self):
        history = {}
        for index in range(30):
            evidence = {
                "generated_at": f"2026-07-11T00:{index:02d}:00+00:00",
                "decision": "HOMOLOGATED",
                "status": "passed",
                "artifact": {"status": "passed"},
                "public_url": {"observed": True, "status": "passed"},
                "errors": [],
            }
            history = build(history, evidence)
        self.assertTrue(history["summary"]["eligible_for_gate_review"])


if __name__ == "__main__":
    unittest.main()
