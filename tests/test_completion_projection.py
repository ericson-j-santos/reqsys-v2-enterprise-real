import json
import unittest
from pathlib import Path

from scripts.generate_completion_projection import (
    COMPLETION_INDICATORS,
    build_completion_projection,
    render_markdown,
)

CONTRACT_PATH = Path("docs/contracts/completion-projection-report.schema.json")


class CompletionProjectionTests(unittest.TestCase):
    def setUp(self):
        self.report = build_completion_projection(
            repository="example/repo",
            run_id="42",
            event_name="workflow_dispatch",
            generated_at="2026-06-27T00:00:00+00:00",
        )

    def test_payload_matches_required_contract_keys(self):
        schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        missing = [key for key in schema["required"] if key not in self.report]
        self.assertEqual(missing, [], f"missing contract keys: {missing}")

    def test_report_only_and_deterministic_aggregates(self):
        self.assertEqual(self.report["mode"], "report_only")
        self.assertEqual(self.report["schema_version"], "1.0.0")
        expected = round(
            sum(item["percent"] for item in COMPLETION_INDICATORS) / len(COMPLETION_INDICATORS) * 10
        ) / 10
        self.assertEqual(self.report["overall_completion_percent"], expected)
        self.assertEqual(self.report["status"], "em_consolidacao")

    def test_probabilities_surface_on_cards(self):
        self.assertEqual(self.report["mvp_probability_percent"], 87)
        self.assertEqual(self.report["enterprise_consolidation_probability_percent"], 61)

    def test_projection_milestones_are_ordered_and_bounded(self):
        for item in self.report["projection_conservative"]:
            self.assertLessEqual(item["days_min"], item["days_max"])
            self.assertIn("estimate_label", item)
        self.assertEqual(len(self.report["projection_conservative"]), 5)
        self.assertEqual(len(self.report["projection_accelerated"]), 5)

    def test_markdown_render_includes_headline_metrics(self):
        markdown = render_markdown(self.report)
        self.assertIn("Completion Projection Report", markdown)
        self.assertIn("Conclusao geral: 63.0%", markdown)
        self.assertIn("Probabilidade MVP forte", markdown)


if __name__ == "__main__":
    unittest.main()
