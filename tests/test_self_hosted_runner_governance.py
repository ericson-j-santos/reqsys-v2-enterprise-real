import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_self_hosted_runner_governance import validate


class SelfHostedRunnerGovernanceTests(unittest.TestCase):
    def make_repo(self) -> tempfile.TemporaryDirectory:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / ".github" / "workflows").mkdir(parents=True)
        return temp

    def test_passes_without_self_hosted_usage(self):
        temp = self.make_repo()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / ".github" / "workflows" / "ci.yml").write_text(
            "jobs:\n  test:\n    runs-on: ubuntu-latest\n", encoding="utf-8"
        )

        ok, result = validate(root, Path(".github/self-hosted-runner-policy.json"))

        self.assertTrue(ok)
        self.assertEqual("pass", result["status"])

    def test_ignores_self_hosted_text_outside_runs_on(self):
        temp = self.make_repo()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / ".github" / "workflows" / "guard.yml").write_text(
            "name: Self-Hosted Runner Governance Guard\n"
            "jobs:\n"
            "  governance:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: python scripts/check_self_hosted_runner_governance.py\n",
            encoding="utf-8",
        )

        ok, result = validate(root, Path(".github/self-hosted-runner-policy.json"))

        self.assertTrue(ok)
        self.assertEqual([], result["self_hosted_usages"])

    def test_blocks_unapproved_self_hosted_usage(self):
        temp = self.make_repo()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / ".github" / "workflows" / "ci.yml").write_text(
            "jobs:\n  test:\n    runs-on: [self-hosted, linux]\n", encoding="utf-8"
        )

        ok, result = validate(root, Path(".github/self-hosted-runner-policy.json"))

        self.assertFalse(ok)
        self.assertTrue(result["violations"])

    def test_blocks_multiline_self_hosted_usage(self):
        temp = self.make_repo()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / ".github" / "workflows" / "ci.yml").write_text(
            "jobs:\n"
            "  test:\n"
            "    runs-on:\n"
            "      - self-hosted\n"
            "      - linux\n",
            encoding="utf-8",
        )

        ok, result = validate(root, Path(".github/self-hosted-runner-policy.json"))

        self.assertFalse(ok)
        self.assertEqual(1, len(result["self_hosted_usages"]))

    def test_requires_adr_and_allowlist_when_enabled(self):
        temp = self.make_repo()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        workflow = ".github/workflows/ci.yml"
        (root / workflow).write_text(
            "jobs:\n  test:\n    runs-on: self-hosted\n", encoding="utf-8"
        )
        (root / ".github" / "self-hosted-runner-policy.json").write_text(
            json.dumps(
                {
                    "self_hosted_allowed": True,
                    "approved_workflows": [workflow],
                    "required_adr": "docs/adr/ADR-999-self-hosted.md",
                }
            ),
            encoding="utf-8",
        )

        ok, result = validate(root, Path(".github/self-hosted-runner-policy.json"))

        self.assertFalse(ok)
        self.assertIn("Required ADR not found", result["violations"][0])


if __name__ == "__main__":
    unittest.main()
