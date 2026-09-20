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

    def test_pr_path_executes_only_dry_run_for_linkedin(self):
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

    def test_default_permissions_are_read_only(self):
        permissions_block = self.text.split("permissions:", 1)[1].split("concurrency:", 1)[0]
        self.assertIn("contents: read", permissions_block)
        self.assertIn("actions: read", permissions_block)
        self.assertNotIn("issues: write", permissions_block)
        self.assertNotIn("contents: write", permissions_block)

    def test_ledger_e2e_scopes_issue_write_to_same_repo_job(self):
        self.assertIn("ledger-e2e:", self.text)
        self.assertIn("Publication Ledger E2E real", self.text)
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", self.text)
        self.assertIn("issues: write", self.text)
        self.assertIn("LEDGER_ISSUE: "1862"", self.text)
        self.assertIn("retry automático não foi bloqueado por PREPARED", self.text)
        self.assertIn('"state": "TEST_CLOSED"', self.text)
        self.assertIn('"linkedin_called": False', self.text)

    def test_ledger_e2e_publishes_dedicated_evidence_artifact(self):
        self.assertIn("name: reqsys-product-story-ledger-e2e", self.text)
        self.assertIn("ledger-e2e.json", self.text)


if __name__ == "__main__":
    unittest.main()
