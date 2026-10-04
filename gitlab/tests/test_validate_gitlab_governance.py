from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_gitlab_governance.py"
SPEC = importlib.util.spec_from_file_location("validate_gitlab_governance", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class FlyRetirementGuardTests(unittest.TestCase):
    def test_repository_has_no_active_gitlab_fly_path(self) -> None:
        self.assertEqual(module.validate_fly_retirement(REPOSITORY_ROOT), [])

    def test_guard_rejects_retired_include_file_and_job(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            ci_dir = root / "gitlab" / "ci"
            ci_dir.mkdir(parents=True)
            (root / ".gitlab-ci.yml").write_text(
                "include:\n  - local: gitlab/ci/deploy.yml\n",
                encoding="utf-8",
            )
            (ci_dir / "deploy.yml").write_text(
                "review_app_deploy:\n  script:\n    - flyctl deploy\n",
                encoding="utf-8",
            )

            issues = module.validate_fly_retirement(root)

        self.assertIn("FORBIDDEN_FLY_FILE: gitlab/ci/deploy.yml", issues)
        self.assertIn("FORBIDDEN_FLY_INCLUDE: gitlab/ci/deploy.yml", issues)
        self.assertIn("FORBIDDEN_FLY_REFERENCE: gitlab/ci/deploy.yml", issues)
        self.assertIn(
            "FORBIDDEN_FLY_JOB: gitlab/ci/deploy.yml: review_app_deploy",
            issues,
        )

    def test_guard_allows_provider_neutral_environment_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            ci_dir = root / "gitlab" / "ci"
            ci_dir.mkdir(parents=True)
            (root / ".gitlab-ci.yml").write_text(
                "include:\n  - local: gitlab/ci/environments.yml\n",
                encoding="utf-8",
            )
            (ci_dir / "environments.yml").write_text(
                "gitlab_environments_baseline:\n  script:\n    - echo baseline\n",
                encoding="utf-8",
            )

            issues = module.validate_fly_retirement(root)

        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
