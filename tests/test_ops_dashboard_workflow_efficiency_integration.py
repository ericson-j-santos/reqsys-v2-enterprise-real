import unittest
from pathlib import Path


WORKFLOW = Path(".github/workflows/ops-dashboard.yml")
DEDICATED_WORKFLOW = Path(".github/workflows/workflow-efficiency-visual-card.yml")


class OpsDashboardWorkflowEfficiencyIntegrationTests(unittest.TestCase):
    def test_main_workflow_compiles_injects_and_validates_visual_card(self):
        content = WORKFLOW.read_text(encoding="utf-8")

        required_fragments = (
            "python -m py_compile scripts/inject_workflow_efficiency_visual_card.py",
            "python -m py_compile scripts/validate_workflow_efficiency_visual_card.py",
            "python scripts/inject_workflow_efficiency_visual_card.py",
            "python scripts/validate_workflow_efficiency_visual_card.py",
            "python3 scripts/validate_workflow_efficiency_visual_card.py",
            'test -f artifacts/ops-dashboard/data/runtime-executive-index.json',
            'test "$(grep -c \'id=\"workflow-efficiency-visual-card\"\' artifacts/ops-dashboard/index.html)" -eq 1',
        )

        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, content)

    def test_injection_happens_before_artifact_packaging(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        injection = content.index("- name: Inject Workflow Efficiency visual card")
        packaging = content.index("- name: Prepare dashboard artifact")
        self.assertLess(injection, packaging)

    def test_parallel_workflow_was_removed(self):
        self.assertFalse(
            DEDICATED_WORKFLOW.exists(),
            "O card deve ser validado exclusivamente pela esteira principal do Ops Dashboard.",
        )


if __name__ == "__main__":
    unittest.main()
