import unittest
from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/executive-promotion-advisor-public-smoke.yml")


class ExecutivePromotionAdvisorPublicSmokeWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_github_pages_deployment_is_explicitly_excluded(self) -> None:
        self.assertIn(
            "github.event.deployment.environment != 'github-pages'",
            self.workflow,
        )

    def test_only_governed_runtime_environments_are_accepted(self) -> None:
        self.assertIn(
            "dev|development|stg|staging|prod|production) ;;",
            self.workflow,
        )
        self.assertNotIn(
            "dev|development|stg|staging|prod|production|github-pages) ;;",
            self.workflow,
        )

    def test_manual_dispatch_does_not_offer_github_pages(self) -> None:
        self.assertIn("options: [dev, stg, prod]", self.workflow)
        self.assertNotIn("options: [dev, stg, prod, github-pages]", self.workflow)


if __name__ == "__main__":
    unittest.main()
