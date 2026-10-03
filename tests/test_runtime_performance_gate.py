from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.runtime_performance_gate import (
    build_report,
    evaluate_budget,
    load_policy,
    percentile,
    run_endpoint,
)


class RuntimePerformanceGateTests(unittest.TestCase):
    def test_percentile_interpolates(self) -> None:
        self.assertEqual(percentile([1, 2, 3, 4], 0.50), 2.5)
        self.assertEqual(percentile([1, 2, 3, 4], 0.95), 3.85)

    def test_percentile_empty_returns_zero(self) -> None:
        self.assertEqual(percentile([], 0.99), 0.0)

    def test_evaluate_budget_detects_latency_and_throughput(self) -> None:
        violations = evaluate_budget(
            {
                "p95_ms": 1600,
                "p99_ms": 2200,
                "error_rate_percent": 0,
                "throughput_rps": 1.5,
            },
            {
                "max_p95_ms": 1500,
                "max_p99_ms": 2500,
                "max_error_rate_percent": 0,
                "min_throughput_rps": 2,
            },
        )
        self.assertEqual(len(violations), 2)
        self.assertTrue(any("p95_ms" in item for item in violations))
        self.assertTrue(any("throughput_rps" in item for item in violations))

    def test_build_report_blocks_when_any_endpoint_blocks(self) -> None:
        report = build_report(
            base_url="https://example.test",
            policy={"policy_version": "1"},
            results=[
                {"status": "passed"},
                {"status": "blocked"},
            ],
            strict=True,
        )
        self.assertEqual(report["summary"]["status"], "blocked")
        self.assertEqual(report["summary"]["endpoints_blocked"], 1)

    def test_load_policy_rejects_mutating_method(self) -> None:
        payload = {
            "schema_version": "1.0.0",
            "endpoints": [
                {
                    "name": "unsafe",
                    "method": "POST",
                    "path": "/api/item",
                    "expected_status": 200,
                    "budget": {},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_policy(path)

    def test_run_endpoint_rejects_retired_provider_before_request(self) -> None:
        endpoint = {
            "name": "health",
            "path": "/health",
            "expected_status": 200,
            "budget": {},
        }
        with (
            patch("scripts.runtime_performance_gate._request_once") as request_once,
            self.assertRaisesRegex(ValueError, "retirado definitivamente"),
        ):
            run_endpoint(
                base_url="https://legacy.fly.dev",
                endpoint=endpoint,
                defaults={"samples": 1, "warmup": 0},
            )
        request_once.assert_not_called()

    def test_run_endpoint_requires_https_before_request(self) -> None:
        endpoint = {
            "name": "health",
            "path": "/health",
            "expected_status": 200,
            "budget": {},
        }
        with (
            patch("scripts.runtime_performance_gate._request_once") as request_once,
            self.assertRaisesRegex(ValueError, "HTTPS"),
        ):
            run_endpoint(
                base_url="http://api.example.net",
                endpoint=endpoint,
                defaults={"samples": 1, "warmup": 0},
            )
        request_once.assert_not_called()


if __name__ == "__main__":
    unittest.main()
