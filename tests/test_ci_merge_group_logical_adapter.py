import tempfile
import unittest
from pathlib import Path

from scripts.audit_critical_workflow_event_coverage import audit


class CiMergeGroupLogicalAdapterTests(unittest.TestCase):
    def test_ci_logical_coverage_uses_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ci.yml").write_text("on:\n  pull_request:\n", encoding="utf-8")
            (root / "ci-merge-group-adapter.yml").write_text(
                "on:\n  merge_group:\n", encoding="utf-8"
            )
            for name in {
                "ci-enterprise-fast.yml",
                "pr-evidence-gate.yml",
                "governed-merge-queue.yml",
                "security-baseline-gate.yml",
            }:
                (root / name).write_text(
                    "on:\n  pull_request:\n  merge_group:\n", encoding="utf-8"
                )

            result = audit(root)
            ci_row = next(row for row in result["workflows"] if row["workflow"] == "ci.yml")

            self.assertTrue(ci_row["pull_request"])
            self.assertTrue(ci_row["merge_group"])
            self.assertEqual(ci_row["coverage_mode"], "logical_adapter")
            self.assertIn("ci-merge-group-adapter.yml", ci_row["coverage_sources"])
            self.assertEqual(result["coverage_percent"], 100)


if __name__ == "__main__":
    unittest.main()
