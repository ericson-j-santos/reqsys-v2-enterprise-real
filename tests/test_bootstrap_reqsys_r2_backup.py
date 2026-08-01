from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "bootstrap_reqsys_r2_backup.py"
SPEC = importlib.util.spec_from_file_location("bootstrap_reqsys_r2_backup", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BackupBootstrapContractTests(unittest.TestCase):
    def test_bucket_validation_accepts_expected_name(self) -> None:
        self.assertEqual(MODULE.validate_bucket("reqsys-backups"), "reqsys-backups")

    def test_bucket_validation_rejects_unsafe_names(self) -> None:
        for value in ("ABCD", "-bucket", "bucket-", "a", "bucket_name", "bucket name"):
            with self.subTest(value=value), self.assertRaises(MODULE.BootstrapError):
                MODULE.validate_bucket(value)

    def test_secret_value_is_sent_only_via_stdin(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=0)
        with patch.object(MODULE.subprocess, "run", return_value=completed) as mocked:
            MODULE.set_actions_secret("owner/repo", "R2_SECRET_ACCESS_KEY", "top-secret")

        kwargs = mocked.call_args.kwargs
        command = mocked.call_args.args[0]
        self.assertNotIn("top-secret", command)
        self.assertEqual(kwargs["input"], "top-secret")
        self.assertIn("R2_SECRET_ACCESS_KEY", command)
        self.assertIn("actions", command)

    def test_required_names_exclude_existing_fly_token(self) -> None:
        self.assertNotIn("FLY_API_TOKEN", MODULE.REQUIRED_SECRET_NAMES)
        self.assertEqual(len(MODULE.REQUIRED_SECRET_NAMES), 5)

    def test_workflows_are_dev_first_and_rollout_guarded(self) -> None:
        self.assertEqual(MODULE.BACKUP_WORKFLOW, "reqsys-free-tier-backup.yml")
        self.assertEqual(MODULE.PROVIDER_WORKFLOW, "reqsys-backup-provider-readiness.yml")
        self.assertEqual(MODULE.ROLLOUT_WORKFLOW, "reqsys-backup-rollout-readiness.yml")


if __name__ == "__main__":
    unittest.main()
