import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.product_intelligence.generate_completion_statistical_projection import (  # noqa: E402
    build_projection,
    main,
    write_reports,
)


class CompletionStatisticalProjectionTests(unittest.TestCase):
    def test_projection_contract_and_summary_metrics(self):
        projection = build_projection()
        summary = projection["statistical_summary"]

        self.assertEqual(projection["schema_version"], "1.0.0")
        self.assertEqual(projection["projection"], "reqsys-completion-statistical-projection")
        self.assertEqual(projection["mode"], "review_only")
        self.assertEqual(projection["reference_timestamp"], "2026-06-27T21:00:00-03:00")
        self.assertEqual(summary["ecosystem_maturity_percent"], 71.2)
        self.assertEqual(summary["real_completion_percent"], 63.0)
        self.assertEqual(summary["remaining_gap_percent"], 24.88)
        self.assertEqual(summary["implemented_to_validated_gap_pp"], 9)
        self.assertEqual(summary["gold_standard_completion_percent"], 52)
        self.assertEqual(summary["gold_standard_gap_percent"], 48)
        self.assertEqual(summary["risk_band"], "MEDIUM_LOW")
        self.assertEqual(summary["probability_index_percent"], 75.5)
        self.assertEqual(summary["mvp_acceleration_gain_days"], 1.5)
        self.assertEqual(summary["enterprise_completion_acceleration_gain_days"], 9.0)
        self.assertEqual(projection["velocity"]["observed"][0]["midpoint"], 13.0)
        self.assertEqual(projection["velocity"]["ci_stabilization_rate_percent"], 83)
        self.assertIn("CI auto-healing", projection["recommended_focus"])
        self.assertEqual(projection["governance"]["deployment"], "disabled")
        self.assertTrue(projection["governance"]["human_review_required"])

    def test_write_reports_creates_json_markdown_and_html(self):
        projection = build_projection()

        with tempfile.TemporaryDirectory() as tmp_dir:
            report_dir = Path(tmp_dir)
            write_reports(projection, report_dir)

            data = json.loads((report_dir / "reqsys-completion-statistical-projection.json").read_text(encoding="utf-8"))
            markdown = (report_dir / "reqsys-completion-statistical-projection.md").read_text(encoding="utf-8")
            html = (report_dir / "reqsys-completion-statistical-projection.html").read_text(encoding="utf-8")

        self.assertEqual(data["statistical_summary"]["real_completion_percent"], 63.0)
        self.assertIn("Padrão ouro total consolidado", markdown)
        self.assertIn("ReqSys — Projeção Estatística de Conclusão", markdown)
        self.assertIn("ReqSys Completion Statistical Projection", html)

    def test_cli_writes_projection_reports(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            report_dir = Path(tmp_dir)
            self.assertEqual(main(["generate_completion_statistical_projection.py", str(report_dir)]), 0)
            payload = json.loads((report_dir / "reqsys-completion-statistical-projection.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["statistical_summary"]["gold_standard_gap_percent"], 48)


if __name__ == "__main__":
    unittest.main()
