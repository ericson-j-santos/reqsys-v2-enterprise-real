import json
import tempfile
import unittest
from pathlib import Path

from tools.product_intelligence.generate_statistical_completion_projection import build_projection, write_reports


class StatisticalCompletionProjectionTests(unittest.TestCase):
    def test_completion_projection_contract_and_priorities(self):
        projection = build_projection()

        self.assertEqual(projection["schema_version"], "1.0.0")
        self.assertEqual(projection["mode"], "review_only")
        self.assertEqual(projection["scores"]["real_completion_score"], 64.0)
        self.assertEqual(projection["scores"]["completion_state"], "ENTERPRISE_ACCELERATING_WITH_GAPS")
        self.assertEqual(projection["scores"]["risk_band"], "MEDIUM_LOW")
        self.assertEqual(projection["bottleneck_priorities"][0]["id"], "environment_sync")
        self.assertEqual(projection["guardrails"]["deployment"], "disabled")
        self.assertTrue(projection["guardrails"]["human_review_required"])

    def test_completion_projection_writes_json_markdown_html_and_doc(self):
        with self.subTest("writes all artifacts"):
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                report_dir = tmp_path / "reports"
                doc_path = tmp_path / "docs" / "reqsys-statistical-completion-projection.md"
                projection = build_projection()

                write_reports(projection, report_dir, doc_path)

                payload = json.loads((report_dir / "reqsys-statistical-completion-projection.json").read_text(encoding="utf-8"))
                markdown = (report_dir / "reqsys-statistical-completion-projection.md").read_text(encoding="utf-8")
                html = (report_dir / "reqsys-statistical-completion-projection.html").read_text(encoding="utf-8")
                doc = doc_path.read_text(encoding="utf-8")

                self.assertEqual(payload["projection"], "reqsys-statistical-completion-projection")
                self.assertIn("ReqSys Statistical Completion Projection", markdown)
                self.assertIn("Gaps prioritarios", markdown)
                self.assertIn("<title>ReqSys Statistical Completion Projection</title>", html)
                self.assertIn("Comando operacional", doc)


if __name__ == "__main__":
    unittest.main()
