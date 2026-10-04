import unittest
from pathlib import Path


WORKFLOWS = (
    Path(".github/workflows/executive-public-smoke-confirmation.yml"),
    Path(".github/workflows/executive-final-sync-history-public-smoke-trend-public.yml"),
    Path(".github/workflows/executive-promotion-advisor-public-smoke.yml"),
)


class ExecutivePublicSmokeDeploymentFilterTests(unittest.TestCase):
    def test_deployment_status_requires_public_environment_url(self) -> None:
        for workflow in WORKFLOWS:
            with self.subTest(workflow=str(workflow)):
                text = workflow.read_text(encoding="utf-8")
                self.assertIn(
                    "github.event.deployment_status.environment_url != ''",
                    text,
                )

    def test_manual_dispatch_and_fail_closed_smoke_are_preserved(self) -> None:
        for workflow in WORKFLOWS:
            with self.subTest(workflow=str(workflow)):
                text = workflow.read_text(encoding="utf-8")
                self.assertIn("workflow_dispatch:", text)
                self.assertIn("deployment_status:", text)
                self.assertRegex(
                    text,
                    r"Enforce (?:confirmed|public) smoke result",
                )


if __name__ == "__main__":
    unittest.main()
