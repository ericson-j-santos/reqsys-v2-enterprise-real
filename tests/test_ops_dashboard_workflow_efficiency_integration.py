import subprocess
import sys
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
            "python scripts/build_pr_workflow_run_metrics.py",
            "python scripts/build_ci_workflow_pareto_recommendations.py",
            "python scripts/build_ci_workflow_efficiency_dashboard.py",
            "python scripts/enrich_reqsys_state_workflow_efficiency.py",
            "python scripts/homologate_workflow_efficiency_artifact.py",
            "python3 scripts/validate_workflow_efficiency_visual_card.py",
            'test -f artifacts/ops-dashboard/data/runtime-executive-index.json',
            'test "$(grep -c \'id=\\"workflow-efficiency-visual-card\\"\' artifacts/ops-dashboard/index.html)" -eq 1',
        )

        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, content)

    def test_direct_workflow_execution_resolves_imports(self):
        result = subprocess.run(
            [sys.executable, "scripts/inject_workflow_efficiency_visual_card.py", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Injeta cards Workflow Efficiency", result.stdout)

    def test_injection_happens_before_artifact_packaging(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        injection = content.index("- name: Inject Workflow Efficiency visual card")
        packaging = content.index("- name: Prepare dashboard artifact")
        self.assertLess(injection, packaging)

    def test_measured_source_and_homologation_precede_publication(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('gh api "/repos/${GITHUB_REPOSITORY}/actions/runs?event=pull_request&per_page=100"', content)
        self.assertIn("sem amostra real de PRs", content)
        self.assertNotIn("Generate synthetic Pareto source", content)
        collect = content.index("- name: Collect measured Workflow Efficiency and enrich canonical index")
        injection = content.index("- name: Inject Workflow Efficiency visual card")
        packaging = content.index("- name: Prepare dashboard artifact")
        homologation = content.index("python scripts/homologate_workflow_efficiency_artifact.py")
        publishing = content.index("- name: Publish ops dashboard artifact")
        self.assertLess(collect, injection)
        self.assertLess(injection, packaging)
        self.assertLess(packaging, homologation)
        self.assertLess(homologation, publishing)

    def test_real_pr_fallback_precedes_metrics_and_preserves_fail_closed(self):
        content = WORKFLOW.read_text(encoding='utf-8')
        collector = content.index('gh api "/repos/${GITHUB_REPOSITORY}/actions/runs?event=pull_request&per_page=100"')
        fallback = content.index('from enrich_ci_pr_efficiency import fetch_recent_pr_sample')
        builder = content.index('python scripts/build_pr_workflow_run_metrics.py')
        gate = content.index('sem amostra real de PRs: proibido fabricar indicador Workflow Efficiency')
        self.assertLess(collector, fallback)
        self.assertLess(fallback, builder)
        self.assertLess(builder, gate)
        self.assertIn("if build_metrics(original)['summary']['pr_count'] == 0:", content)
        self.assertIn("if recovered and sample['target_met']:", content)
        self.assertIn('min_sample_prs=3', content)
        self.assertIn('max_age_days=7', content)
        self.assertIn("snapshot.with_name('workflow-runs-global.json').write_bytes", content)
        self.assertIn("'source': 'github_pr_commit_runs'", content)
        self.assertNotIn('Generate synthetic Pareto source', content)

    def test_parallel_workflow_was_removed(self):
        self.assertFalse(
            DEDICATED_WORKFLOW.exists(),
            "O card deve ser validado exclusivamente pela esteira principal do Ops Dashboard.",
        )


if __name__ == "__main__":
    unittest.main()
