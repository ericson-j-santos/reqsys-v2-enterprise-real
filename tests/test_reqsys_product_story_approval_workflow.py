import unittest
from pathlib import Path


WORKFLOW = Path(".github/workflows/reqsys-product-story-approval.yml")


class ReqSysProductStoryApprovalWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_has_human_dispatch_contract(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertIn("content_hash:", self.text)
        self.assertIn("author_urn:", self.text)
        self.assertIn("confirmation:", self.text)
        self.assertIn("approved_by=$GITHUB_ACTOR", self.text)

    def test_pr_path_executes_only_dry_run(self):
        self.assertIn("pull_request:", self.text)
        self.assertIn("--mode dry_run", self.text)
        self.assertNotIn("--mode publish", self.text)
        self.assertNotIn("LINKEDIN_ACCESS_TOKEN", self.text)
        self.assertNotIn("REQSYS_LINKEDIN_PUBLISH_ENABLED", self.text)

    def test_regenerates_candidates_from_weekly_main_evidence(self):
        self.assertIn("reqsys-weekly-accomplishment-log.yml", self.text)
        self.assertIn("--branch main", self.text)
        self.assertIn("scripts/reqsys_product_story_engine.py", self.text)

    def test_has_negative_control_and_independent_read(self):
        self.assertIn("Controle negativo", self.text)
        self.assertIn('--confirmation "DENY"', self.text)
        self.assertIn("Leitura independente da evidência", self.text)
        self.assertIn('p["published"] is False', self.text)

    def test_permissions_remain_read_only(self):
        self.assertIn("contents: read", self.text)
        self.assertIn("actions: read", self.text)
        self.assertNotIn("contents: write", self.text)


if __name__ == "__main__":
    unittest.main()
