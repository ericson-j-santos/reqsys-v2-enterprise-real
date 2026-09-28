#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from enrich_ci_reliability_evidence import (  # noqa: E402
    SECTION_MARKER,
    collect_reliability_baseline,
    enrich_files,
)


def analytics(prs):
    return {
        "schema_version": "1.0.5",
        "pr_efficiency": {
            "baseline_sample_valid": True,
            "blocking_workflows": ["Required A"],
            "prs": prs,
        },
    }


def run(run_id, *, sha, attempt=1, conclusion="success"):
    return {
        "id": run_id,
        "name": "Required A",
        "event": "pull_request",
        "status": "completed",
        "conclusion": conclusion,
        "head_sha": sha,
        "run_attempt": attempt,
        "updated_at": "2026-09-27T20:00:00Z",
    }


class CiReliabilityEvidenceTests(unittest.TestCase):
    def test_detects_flaky_unresolved_from_divergent_attempts(self):
        head = "a" * 40

        def fake_api(path, token):
            self.assertEqual(token, "token")
            if path.endswith("/pulls/10"):
                return {"head": {"sha": head}}
            if "actions/runs?head_sha=" in path:
                return {"workflow_runs": [run(100, sha=head, attempt=2)]}
            if path.endswith("/runs/100/attempts/1"):
                return {"status": "completed", "conclusion": "failure"}
            if path.endswith("/runs/100/attempts/2"):
                return {"status": "completed", "conclusion": "success"}
            if path.endswith("/runs/100/jobs?per_page=100"):
                return {
                    "total_count": 1,
                    "jobs": [
                        {
                            "id": 1,
                            "name": "test",
                            "status": "completed",
                            "conclusion": "success",
                            "runner_name": "GitHub Actions 1",
                            "started_at": "2026-09-27T19:59:00Z",
                        }
                    ],
                }
            raise AssertionError(path)

        result = collect_reliability_baseline(
            analytics([{"pr_number": 10, "latest_head_sha": head}]),
            owner="owner",
            name="repo",
            token="token",
            api_get=fake_api,
        )
        self.assertTrue(result["baseline_sample_valid"])
        self.assertEqual(result["flaky_unresolved_runs"], 1)
        self.assertEqual(result["sha_divergent_prs"], 0)
        self.assertEqual(result["pickup_unproven_runs"], 0)
        self.assertIn(
            "FLAKY_UNRESOLVED",
            result["prs"][0]["runs"][0]["findings"],
        )

    def test_detects_sha_divergence_and_unproven_pickup(self):
        observed = "a" * 40
        expected = "b" * 40

        def fake_api(path, token):
            if path.endswith("/pulls/11"):
                return {"head": {"sha": expected}}
            if "actions/runs?head_sha=" in path:
                return {"workflow_runs": [run(101, sha=observed)]}
            if path.endswith("/runs/101/attempts/1"):
                return {"status": "completed", "conclusion": "success"}
            if path.endswith("/runs/101/jobs?per_page=100"):
                return {
                    "total_count": 1,
                    "jobs": [
                        {
                            "id": 2,
                            "name": "queued-never-picked",
                            "status": "completed",
                            "conclusion": "cancelled",
                            "runner_name": "",
                            "started_at": "",
                        }
                    ],
                }
            raise AssertionError(path)

        result = collect_reliability_baseline(
            analytics([{"pr_number": 11, "latest_head_sha": observed}]),
            owner="owner",
            name="repo",
            token="token",
            api_get=fake_api,
        )
        self.assertEqual(result["sha_divergent_prs"], 1)
        self.assertEqual(result["pickup_unproven_runs"], 1)
        self.assertIn("SHA_DIVERGENT", result["prs"][0]["findings"])
        self.assertIn(
            "PICKUP_UNPROVEN",
            result["prs"][0]["runs"][0]["findings"],
        )

    def test_incomplete_jobs_collection_fails_closed(self):
        head = "a" * 40

        def fake_api(path, token):
            if path.endswith("/pulls/12"):
                return {"head": {"sha": head}}
            if "actions/runs?head_sha=" in path:
                return {"workflow_runs": [run(102, sha=head)]}
            if path.endswith("/runs/102/attempts/1"):
                return {"status": "completed", "conclusion": "success"}
            if path.endswith("/runs/102/jobs?per_page=100"):
                return {"total_count": 2, "jobs": [{"id": 1}]}
            raise AssertionError(path)

        with self.assertRaisesRegex(RuntimeError, "coleta de jobs incompleta"):
            collect_reliability_baseline(
                analytics([{"pr_number": 12, "latest_head_sha": head}]),
                owner="owner",
                name="repo",
                token="token",
                api_get=fake_api,
            )

    def test_enrichment_is_idempotent_and_report_only(self):
        metrics = {
            "contract": "ci-reliability-evidence.v1",
            "mode": "report-only",
            "creates_gate": False,
            "available": True,
            "baseline_sample_valid": True,
            "sampled_prs": 1,
            "sampled_runs": 1,
            "flaky_unresolved_runs": 0,
            "sha_divergent_prs": 0,
            "pickup_unproven_runs": 0,
            "semantics": {},
            "prs": [],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            analytics_path = root / "analytics.json"
            markdown_path = root / "analytics.md"
            analytics_path.write_text(
                json.dumps({"schema_version": "1.0.5"}),
                encoding="utf-8",
            )
            markdown_path.write_text("# CI\n", encoding="utf-8")

            enrich_files(analytics_path, markdown_path, metrics)
            enrich_files(analytics_path, markdown_path, metrics)

            payload = json.loads(analytics_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "1.0.6")
            self.assertFalse(payload["ci_reliability_evidence"]["creates_gate"])
            self.assertEqual(
                markdown_path.read_text(encoding="utf-8").count(SECTION_MARKER),
                1,
            )


if __name__ == "__main__":
    unittest.main()
