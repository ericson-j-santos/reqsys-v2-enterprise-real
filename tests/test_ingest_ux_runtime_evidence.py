import unittest
from datetime import datetime, timezone

from scripts.ingest_ux_runtime_evidence import ingest_history, normalize_evidence


class RuntimeEvidenceIngestionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 7, 15, 18, 30, tzinfo=timezone.utc)
        self.report = {
            "recovery_rate": 80,
            "average_recovery_seconds": 22,
            "ux_100_ready": True,
        }
        self.metadata = {
            "origin": "post-merge-smoke",
            "environment": "stg",
            "timestamp": "2026-07-15T18:20:00Z",
            "correlation_id": "reqsys-runtime-20260715-001",
            "merge_sha": "a" * 40,
        }

    def test_promotes_only_verified_evidence_to_runtime(self):
        evidence = normalize_evidence(self.report, self.metadata, now=self.now)
        self.assertEqual(evidence["evidence_source"], "runtime")
        self.assertEqual(evidence["verification_status"], "verified")
        self.assertEqual(evidence["verification_reasons"], [])

        history, audit = ingest_history([], evidence)
        self.assertEqual(len(history), 1)
        self.assertTrue(audit["accepted"])
        self.assertFalse(audit["production_blocker"])

    def test_rejects_missing_correlation_id_without_polluting_history(self):
        metadata = dict(self.metadata)
        metadata.pop("correlation_id")
        evidence = normalize_evidence(self.report, metadata, now=self.now)
        self.assertEqual(evidence["evidence_source"], "unverified")
        self.assertIn("correlation_id_not_verified", evidence["verification_reasons"])

        history, audit = ingest_history([], evidence)
        self.assertEqual(history, [])
        self.assertFalse(audit["accepted"])

    def test_rejects_unapproved_environment_and_origin(self):
        metadata = dict(self.metadata, environment="local", origin="manual")
        evidence = normalize_evidence(self.report, metadata, now=self.now)
        self.assertIn("origin_not_verified", evidence["verification_reasons"])
        self.assertIn("environment_not_verified", evidence["verification_reasons"])

    def test_deduplicates_same_runtime_execution(self):
        evidence = normalize_evidence(self.report, self.metadata, now=self.now)
        history, _ = ingest_history([], evidence)
        history, audit = ingest_history(history, evidence)
        self.assertEqual(len(history), 1)
        self.assertTrue(audit["duplicate"])


if __name__ == "__main__":
    unittest.main()
