import unittest
from pathlib import Path


WORKFLOW = Path(".github/workflows/reqsys-product-story-engine.yml")


class ReqSysProductStoryWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_is_event_driven_from_weekly_evidence(self):
        self.assertIn("workflow_run:", self.text)
        self.assertIn("ReqSys Weekly Accomplishment Log", self.text)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", self.text)

    def test_downloads_exact_source_artifact(self):
        self.assertIn("--name reqsys-weekly-accomplishment-log", self.text)
        self.assertIn("reqsys-weekly-accomplishment-log.json", self.text)

    def test_generates_review_artifact_without_publish_step(self):
        self.assertIn("scripts/reqsys_product_story_engine.py", self.text)
        self.assertIn("name: reqsys-product-story-engine", self.text)
        lowered = self.text.casefold()
        self.assertNotIn("linkedin.com", lowered)
        self.assertNotIn("w_member_social", lowered)
        self.assertNotIn("w_organization_social", lowered)

    def test_permissions_are_read_only(self):
        self.assertIn("contents: read", self.text)
        self.assertIn("actions: read", self.text)
        self.assertNotIn("contents: write", self.text)


if __name__ == "__main__":
    unittest.main()
