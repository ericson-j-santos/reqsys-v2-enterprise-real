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
        self.assertIn("dev|development)", self.workflow)
        self.assertIn("stg|staging)", self.workflow)
        self.assertIn("prod|production)", self.workflow)
        self.assertIn(
            '*) echo "Ambiente não governado: $TARGET_ENVIRONMENT" >&2; exit 1 ;;',
            self.workflow,
        )
        self.assertNotIn("github-pages)", self.workflow)

    def test_governed_environment_fallback_urls_are_defined(self) -> None:
        self.assertIn("https://reqsys-app-dev.fly.dev", self.workflow)
        self.assertIn("https://reqsys-app-stg.fly.dev", self.workflow)
        self.assertIn("https://reqsys-app.fly.dev", self.workflow)
        self.assertIn('echo "TARGET_URL=$resolved_url" >> "$GITHUB_ENV"', self.workflow)

    def test_manual_dispatch_does_not_offer_github_pages(self) -> None:
        self.assertIn("options: [dev, stg, prod]", self.workflow)
        self.assertNotIn("options: [dev, stg, prod, github-pages]", self.workflow)


if __name__ == "__main__":
    unittest.main()
