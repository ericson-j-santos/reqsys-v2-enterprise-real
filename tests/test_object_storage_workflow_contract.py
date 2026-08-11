from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKUP_WORKFLOW = ROOT / ".github/workflows/reqsys-free-tier-backup.yml"
READINESS_WORKFLOW = ROOT / ".github/workflows/reqsys-backup-provider-readiness.yml"
INVENTORY = ROOT / "governance/backup/reqsys-backup-assets.json"


class ObjectStorageWorkflowContractTests(unittest.TestCase):
    def test_backup_supports_generic_s3_contract_and_r2_rollback(self) -> None:
        workflow = BACKUP_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("OBJECT_STORAGE_ACCESS_KEY_ID", workflow)
        self.assertIn("OBJECT_STORAGE_SECRET_ACCESS_KEY", workflow)
        self.assertIn("OBJECT_STORAGE_BUCKET", workflow)
        self.assertIn("https://fly.storage.tigris.dev", workflow)
        self.assertIn("secrets.R2_ACCESS_KEY_ID", workflow)
        self.assertIn("R2_ACCOUNT_ID", workflow)
        self.assertNotIn("RESTIC_REPOSITORY: s3:https://${{ secrets.R2_ACCOUNT_ID }}", workflow)

    def test_readiness_uses_provider_neutral_secrets(self) -> None:
        workflow = READINESS_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "FLY_API_TOKEN,OBJECT_STORAGE_ACCESS_KEY_ID,"
            "OBJECT_STORAGE_SECRET_ACCESS_KEY,OBJECT_STORAGE_BUCKET,RESTIC_PASSWORD",
            workflow,
        )
        self.assertIn("Probe private S3-compatible bucket", workflow)
        self.assertNotIn("Probe private R2 bucket", workflow)

    def test_inventory_applies_tigris_free_tier_guardrail(self) -> None:
        inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
        storage = inventory["storage"]
        self.assertEqual("tigris", storage["provider"])
        self.assertEqual(4 * 1024**3, storage["free_tier_warn_bytes"])
        self.assertEqual(int(4.5 * 1024**3), storage["free_tier_hard_bytes"])
        self.assertLess(storage["free_tier_warn_bytes"], storage["free_tier_hard_bytes"])


if __name__ == "__main__":
    unittest.main()
