import json
import tempfile
import unittest
from pathlib import Path

from scripts.homologate_workflow_efficiency_artifact import homologate


class WorkflowEfficiencyArtifactHomologationTests(unittest.TestCase):
    def build_fixture(self, root: Path, *, include_card: bool = True) -> None:
        (root / "data").mkdir(parents=True)
        html = '''<!doctype html><html><body>
<section id="workflow-efficiency-visual-card"></section>
<script>
function renderWorkflowEfficiency(payload) {
  const card = payload?.cards?.workflow_efficiency;
  const link = payload?.links?.workflow_efficiency;
  return card || link;
}
renderWorkflowEfficiency(payload);
</script>
</body></html>'''
        (root / "index.html").write_text(html, encoding="utf-8")
        payload = {
            "cards": {
                "workflow_efficiency": {
                    "status": "healthy",
                    "score_percent": 92.5,
                    "mode": "report-only",
                }
            } if include_card else {},
            "links": {
                "workflow_efficiency": "data/ci-workflow-efficiency-dashboard.json"
            } if include_card else {},
        }
        (root / "data" / "runtime-executive-index.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def test_homologates_complete_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.build_fixture(root)
            evidence = homologate(root, "test-123")

            self.assertEqual(evidence["status"], "passed")
            self.assertEqual(evidence["decision"], "HOMOLOGATED")
            self.assertEqual(evidence["correlation_id"], "test-123")
            self.assertEqual(evidence["workflow_efficiency"]["score_percent"], 92.5)
            self.assertEqual(evidence["checks"]["html_card_count"], 1)
            self.assertTrue(evidence["checks"]["contract_card_present"])

    def test_blocks_missing_contract_card(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.build_fixture(root, include_card=False)
            evidence = homologate(root, "test-456")

            self.assertEqual(evidence["status"], "failed")
            self.assertEqual(evidence["decision"], "BLOCKED")
            self.assertIn("cards.workflow_efficiency ausente ou vazio", evidence["errors"])

    def test_blocks_missing_artifact_files(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = homologate(Path(directory), "test-789")

            self.assertEqual(evidence["status"], "failed")
            self.assertEqual(len(evidence["errors"]), 2)


if __name__ == "__main__":
    unittest.main()
