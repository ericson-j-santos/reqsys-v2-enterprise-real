import tempfile
import unittest
from pathlib import Path

from scripts.audit_critical_workflow_event_coverage import audit


class CriticalWorkflowEventCoverageTests(unittest.TestCase):
    def test_complete_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "critical.yml").write_text(
                "on:\n  pull_request:\n  merge_group:\n", encoding="utf-8"
            )
            result = audit(root, {"critical.yml"})
            self.assertEqual(result["status"], "COVERAGE_COMPLETE")
            self.assertTrue(result["throughput_increase_allowed"])

    def test_gap_blocks_throughput_increase(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "critical.yml").write_text("on:\n  pull_request:\n", encoding="utf-8")
            result = audit(root, {"critical.yml"})
            self.assertEqual(result["status"], "COVERAGE_GAPS_FOUND")
            self.assertFalse(result["throughput_increase_allowed"])
            self.assertEqual(result["coverage_percent"], 0)

    def test_missing_workflow_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            result = audit(Path(directory), {"missing.yml"})
            self.assertFalse(result["workflows"][0]["exists"])


if __name__ == "__main__":
    unittest.main()
