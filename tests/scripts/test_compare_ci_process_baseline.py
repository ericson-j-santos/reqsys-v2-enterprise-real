#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from compare_ci_process_baseline import (  # noqa: E402
    apply_baseline_comparison,
    build_baseline_comparison,
    load_frozen_baseline,
)


def summary_fixture(repository="owner/repo"):
    return {
        "schema_version": "1.0.2",
        "repository": repository,
        "success_rate_percent": 90.0,
        "failure_rate_percent": 4.0,
        "first_pass_success_rate_percent": 88.0,
        "rerun_rate_percent": 2.0,
        "avg_seconds": 15.0,
        "p50_seconds": 10.0,
        "p95_seconds": 30.0,
        "p95_queue_seconds": 0.0,
        "stddev_seconds": 15.0,
        "cv_percent": 80.0,
    }


def baseline_fixture(repository="owner/repo"):
    return {
        "frozen": True,
        "frozen_at": "2026-09-02T22:58:32+00:00",
        "source": {
            "repository": repository,
            "workflow_run_id": 33692899180,
            "workflow_run_number": 1154,
            "head_sha": "cf467cd5",
            "analytics_schema_version": "1.0.2",
        },
        "quality": {
            "success_rate_percent": 77.42,
            "failure_rate_percent": 6.45,
            "first_pass_success_rate_percent": 77.42,
            "rerun_rate_percent": 0.0,
        },
        "time": {
            "avg_seconds": 18.89,
            "p50_seconds": 14.0,
            "p95_seconds": 38.9,
            "stddev_seconds": 21.32,
            "cv_percent": 112.91,
            "p95_queue_seconds": 0.0,
        },
        "governance": {"mode": "report-only"},
    }


class BaselineComparisonTests(unittest.TestCase):
    def test_groups_quality_speed_and_variability_without_gate(self):
        comparison = build_baseline_comparison(summary_fixture(), baseline_fixture(), baseline_path="baseline.json")
        self.assertTrue(comparison["available"])
        self.assertEqual(comparison["mode"], "report-only")
        self.assertFalse(comparison["creates_gate"])
        self.assertIn("quality", comparison["delta"])
        self.assertIn("speed", comparison["delta"])
        self.assertIn("variability", comparison["delta"])
        self.assertEqual(comparison["signals"]["speed"]["p95"], "improved")

    def test_missing_baseline_does_not_break_reporting(self):
        comparison = build_baseline_comparison(summary_fixture(), None, baseline_path="missing.json")
        self.assertFalse(comparison["available"])
        self.assertEqual(comparison["mode"], "report-only")
        self.assertFalse(comparison["creates_gate"])

    def test_mutable_baseline_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.json"
            path.write_text('{"frozen": false, "governance": {"mode": "report-only"}}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_frozen_baseline(path)

    def test_apply_upgrades_artifact_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            analytics = root / "analytics.json"
            markdown = root / "analytics.md"
            baseline = root / "baseline.json"
            analytics.write_text(json.dumps(summary_fixture()), encoding="utf-8")
            markdown.write_text("# CI Lead Time Analytics\n", encoding="utf-8")
            baseline.write_text(json.dumps(baseline_fixture()), encoding="utf-8")
            first = apply_baseline_comparison(analytics, markdown, baseline)
            second = apply_baseline_comparison(analytics, markdown, baseline)
            self.assertEqual(first["schema_version"], "1.0.3")
            self.assertEqual(second["schema_version"], "1.0.3")
            text = markdown.read_text(encoding="utf-8")
            self.assertEqual(text.count("## Frozen baseline comparison"), 1)
            self.assertIn("Gate created: no", text)

    def test_repository_baseline_remains_frozen_reference(self):
        path = ROOT / "audit/baselines/ci-process-improvement-baseline-2026-09-02.json"
        baseline = load_frozen_baseline(path)
        self.assertEqual(baseline["source"]["workflow_run_id"], 33692899180)
        self.assertEqual(baseline["quality"]["success_rate_percent"], 77.42)
        self.assertEqual(baseline["time"]["p95_seconds"], 38.9)
        self.assertEqual(baseline["governance"]["mode"], "report-only")


if __name__ == "__main__":
    unittest.main()
