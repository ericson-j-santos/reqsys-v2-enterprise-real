from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("business_impact", ROOT/"scripts"/"business_impact_telemetry.py")
mod=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(mod)

class BusinessImpactTelemetryTests(unittest.TestCase):
    def test_observed_metrics_and_unavailable_roi(self):
        report=mod.analyze(
            [{"created_at":"2026-10-01T10:00:00Z","merged_at":"2026-10-01T11:30:00Z"}],
            [{"failed_at":"2026-10-01T10:15:00Z","recovered_at":"2026-10-01T10:45:00Z"}],
            source_sha="a"*40,
        )
        self.assertEqual(report["metrics"]["pr_to_merge_minutes"]["median"],90.0)
        self.assertEqual(report["metrics"]["failure_to_recovery_minutes"]["median"],30.0)
        self.assertEqual(report["metrics"]["roi_percent"]["status"],"unavailable")
        self.assertEqual(report["measurement_policy"],"observed_only_no_roi_estimation")

    def test_invalid_or_missing_evidence_does_not_create_metrics(self):
        report=mod.analyze(
            [{"created_at":"2026-10-01T11:00:00Z","merged_at":"2026-10-01T10:00:00Z"}],
            [{"failed_at":None,"recovered_at":"2026-10-01T10:45:00Z"}],
            source_sha="b"*40,
        )
        self.assertEqual(report["metrics"]["pr_to_merge_minutes"]["status"],"unavailable")
        self.assertEqual(report["metrics"]["failure_to_recovery_minutes"]["status"],"unavailable")

if __name__=="__main__":
    unittest.main()
