from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.remote_sqlite_backup import create_backup
from scripts.reqsys_free_tier_backup import (
    dashboard as build_dashboard,
    evidence as build_evidence,
    markdown as dashboard_markdown,
    quota as evaluate_quota,
    merged,
    select,
    manifest as sqlite_manifest,
    validate_inventory,
)


class ReqSysFreeTierBackupTests(unittest.TestCase):
    def inventory(self) -> dict[str, object]:
        return json.loads(Path("governance/backup/reqsys-backup-assets.json").read_text())

    def test_inventory_is_valid_and_dev_is_only_enabled_asset(self) -> None:
        inventory = self.inventory()
        self.assertEqual(validate_inventory(inventory), [])
        selected = select(inventory, "all", include_disabled=False)
        self.assertEqual([asset["environment"] for asset in selected], ["dev"])
        prod = select(inventory, "prod", include_disabled=True)[0]
        self.assertEqual(merged(inventory, prod)["database_path"], "/data/reqsys.db")

    def test_consistent_sqlite_backup_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.db"
            backup = root / "backup.db"
            metadata = root / "metadata.json"
            with sqlite3.connect(source) as connection:
                connection.execute("CREATE TABLE item(id INTEGER PRIMARY KEY, name TEXT)")
                connection.executemany("INSERT INTO item(name) VALUES (?)", [("a",), ("b",)])
            remote = create_backup(source, backup, metadata)
            local = sqlite_manifest(backup)
            self.assertEqual(remote["quick_check"], "ok")
            self.assertEqual(local["row_count_total"], 2)
            self.assertEqual(remote["sha256"], local["sha256"])

    def test_quota_guard(self) -> None:
        self.assertEqual(evaluate_quota(1, 8, 9)["status"], "healthy")
        self.assertEqual(evaluate_quota(8, 8, 9)["status"], "warning")
        self.assertEqual(evaluate_quota(9, 8, 9)["status"], "critical")

    def test_evidence_requires_identical_restore(self) -> None:
        inventory = self.inventory()
        asset = select(inventory, "dev", False)[0]
        manifest = {
            "quick_check": "ok",
            "sha256": "a" * 64,
            "table_counts": {"item": 2},
            "row_count_total": 2,
        }
        result = build_evidence(
            asset,
            manifest,
            dict(manifest),
            {"status":"healthy","total_size_bytes":100,"warn_bytes":800,"hard_bytes":900,"utilization_percent":11.111},
            "snapshot-1",
            "https://example.test/run",
            "corr-1",
            "2026-08-01T00:00:00+00:00",
            "2026-08-01T00:00:01+00:00",
            1.0,
        )
        self.assertEqual(result["result"], "passed")
        self.assertTrue(result["integrity_match"])
        self.assertNotIn("table_counts", result["source_manifest"])
        self.assertIn("table_counts_sha256", result["source_manifest"])

    def test_dashboard_reports_configuration_block(self) -> None:
        result = build_dashboard(
            self.inventory(), [], False, ["R2_ACCESS_KEY_ID"], "https://example.test/run", "skipped"
        )
        self.assertEqual(result["health"], "warning")
        self.assertEqual(result["assets"][0]["status"], "blocked_configuration")
        self.assertIn("R2_ACCESS_KEY_ID", dashboard_markdown(result))

    def test_dashboard_marks_failed_execution_critical(self) -> None:
        result = build_dashboard(
            self.inventory(), [], True, [], "https://example.test/run", "failure"
        )
        self.assertEqual(result["health"], "critical")
        self.assertEqual(result["assets"][0]["status"], "critical")


if __name__ == "__main__":
    unittest.main()
