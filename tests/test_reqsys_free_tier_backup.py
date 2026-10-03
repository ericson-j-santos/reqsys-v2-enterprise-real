from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.remote_sqlite_backup import create_backup
from scripts.reqsys_free_tier_backup import dashboard as build_dashboard
from scripts.reqsys_free_tier_backup import evidence as build_evidence
from scripts.reqsys_free_tier_backup import manifest as sqlite_manifest
from scripts.reqsys_free_tier_backup import markdown as dashboard_markdown
from scripts.reqsys_free_tier_backup import merged, select, validate_inventory
from scripts.reqsys_free_tier_backup import quota as evaluate_quota


class ReqSysFreeTierBackupTests(unittest.TestCase):
    def inventory(self) -> dict[str, object]:
        return json.loads(Path("governance/backup/reqsys-backup-assets.json").read_text())

    def test_inventory_is_valid_for_governed_rollout(self) -> None:
        inventory = self.inventory()
        self.assertEqual(validate_inventory(inventory), [])
        selected = select(inventory, "all", include_disabled=False)
        selected_envs = [asset["environment"] for asset in selected]

        stg = next(asset for asset in inventory["assets"] if asset["environment"] == "stg")
        self.assertFalse(stg["enabled"])
        self.assertEqual(stg["rollout_state"], "retired_flyio_2026-10-02")
        self.assertEqual(stg["rollout_evidence"]["decision"], "stg_rollout_candidate")
        self.assertFalse(stg["rollout_evidence"]["production_allowed"])
        self.assertTrue(str(stg["rollout_evidence"]["source_run_id"]).isdigit())

        prod = next(asset for asset in inventory["assets"] if asset["environment"] == "prod")
        self.assertFalse(prod["enabled"])
        self.assertEqual(selected_envs, [])
        self.assertEqual(prod["rollout_state"], "retired_flyio_2026-10-02")
        evidence = prod["rollout_evidence"]
        self.assertEqual(evidence["source_environment"], "stg")
        self.assertEqual(
            evidence["decision"],
            "prod_rollout_candidate_requires_approval",
        )
        self.assertEqual(
            evidence["human_approval_mode"],
            "workflow_dispatch_APROVO-PROD",
        )
        self.assertFalse(evidence["production_allowed"])
        self.assertTrue(str(evidence["source_run_id"]).isdigit())
        self.assertTrue(str(evidence["source_artifact_digest"]).startswith("sha256:"))

        selected_prod = select(inventory, "prod", include_disabled=True)[0]
        self.assertEqual(merged(inventory, selected_prod)["database_path"], "/data/reqsys.db")
        self.assertNotIn("fly_app", selected_prod)
        self.assertEqual(selected_prod["rollout_state"], "retired_legacy_provider")

    def test_consistent_sqlite_backup_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.db"
            backup = root / "backup.db"
            metadata = root / "metadata.json"
            with closing(sqlite3.connect(source)) as connection:
                connection.execute("CREATE TABLE item(id INTEGER PRIMARY KEY, name TEXT)")
                connection.executemany(
                    "INSERT INTO item(name) VALUES (?)",
                    [("a",), ("b",)],
                )
                connection.commit()
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
        asset = select(inventory, "dev", include_disabled=True)[0]
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
            {
                "status": "healthy",
                "total_size_bytes": 100,
                "warn_bytes": 800,
                "hard_bytes": 900,
                "utilization_percent": 11.111,
            },
            "snapshot-1",
            "https://example.test/run",
            "corr-1",
            "2026-08-01T00:00:00+00:00",
            "2026-08-01T00:00:01+00:00",
            1.0,
        )
        self.assertEqual(result["result"], "passed")
        self.assertTrue(result["integrity_match"])
        self.assertNotIn("fly_app", result)
        self.assertNotIn("table_counts", result["source_manifest"])
        self.assertIn("table_counts_sha256", result["source_manifest"])

    def test_dashboard_reports_configuration_block(self) -> None:
        inventory = self.inventory()
        inventory["assets"][0]["enabled"] = True
        result = build_dashboard(
            inventory,
            [],
            False,
            ["R2_ACCESS_KEY_ID"],
            "https://example.test/run",
            "skipped",
        )
        self.assertEqual(result["health"], "warning")
        self.assertEqual(result["assets"][0]["status"], "blocked_configuration")
        self.assertTrue(all("fly_app" not in item for item in result["assets"]))
        markdown = dashboard_markdown(result)
        self.assertIn("R2_ACCESS_KEY_ID", markdown)
        self.assertIn("quota alerta em 4 GiB e bloqueia em 4.5 GiB", markdown)
        self.assertNotIn("quota alerta em 8 GiB e bloqueia em 9 GiB", markdown)

    def test_dashboard_marks_failed_execution_critical(self) -> None:
        inventory = self.inventory()
        inventory["assets"][0]["enabled"] = True
        result = build_dashboard(
            inventory,
            [],
            True,
            [],
            "https://example.test/run",
            "failure",
        )
        self.assertEqual(result["health"], "critical")
        self.assertEqual(result["assets"][0]["status"], "critical")


if __name__ == "__main__":
    unittest.main()
