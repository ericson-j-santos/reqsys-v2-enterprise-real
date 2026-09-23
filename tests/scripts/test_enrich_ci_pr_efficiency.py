#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from enrich_ci_pr_efficiency import (  # noqa: E402
    SECTION_MARKER,
    build_pr_efficiency,
    enrich_files,
    load_blocking_workflows,
)


START = datetime(2026, 9, 22, 15, 0, tzinfo=timezone.utc)
END = datetime(2026, 9, 22, 16, 0, tzinfo=timezone.utc)
BLOCKING = ["Required A", "Required B"]


def run(
    idx: int,
    *,
    pr: int | None,
    name: str,
    sha: str,
    created: str,
    updated: str,
    conclusion: str = "success",
    event: str = "pull_request",
    attempt: int = 1,
):
    return {
        "id": idx,
        "name": name,
        "event": event,
        "status": "completed",
        "conclusion": conclusion,
        "head_branch": "feature/test",
        "head_sha": sha,
        "html_url": f"https://example.test/{idx}",
        "created_at": created,
        "run_started_at": created,
        "updated_at": updated,
        "run_attempt": attempt,
        "pull_requests": [] if pr is None else [{"number": pr}],
    }


class CiPrEfficiencyTests(unittest.TestCase):
    def test_calculates_minutes_time_to_green_and_workflow_pareto(self):
        raw = [
            run(
                1,
                pr=10,
                name="Required A",
                sha="sha-10",
                created="2026-09-22T15:05:00Z",
                updated="2026-09-22T15:09:00Z",
            ),
            run(
                2,
                pr=10,
                name="Required B",
                sha="sha-10",
                created="2026-09-22T15:05:00Z",
                updated="2026-09-22T15:06:00Z",
            ),
            run(
                3,
                pr=11,
                name="Required A",
                sha="sha-11",
                created="2026-09-22T15:10:00Z",
                updated="2026-09-22T15:12:00Z",
            ),
            run(
                4,
                pr=11,
                name="Required B",
                sha="sha-11",
                created="2026-09-22T15:10:00Z",
                updated="2026-09-22T15:12:00Z",
            ),
        ]
        result = build_pr_efficiency(
            raw,
            blocking_workflows=BLOCKING,
            start_at=START,
            end_at=END,
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["sample_prs"], 2)
        self.assertEqual(result["green_sample_prs"], 2)
        self.assertEqual(result["total_observed_ci_run_minutes"], 9.0)
        self.assertEqual(result["avg_observed_ci_run_minutes_per_pr"], 4.5)
        self.assertEqual(result["p50_observed_ci_run_minutes_per_pr"], 4.5)
        self.assertEqual(result["p90_observed_ci_run_minutes_per_pr"], 4.9)
        self.assertEqual(result["p50_latest_head_time_to_green_seconds"], 180.0)
        self.assertEqual(result["p90_latest_head_time_to_green_seconds"], 228.0)
        self.assertEqual(result["workflows_to_80_percent"]["count"], 2)
        self.assertEqual(
            result["workflows_to_80_percent"]["names"],
            ["Required A", "Required B"],
        )
        self.assertEqual(
            result["workflow_minutes_pareto"][-1]["cumulative_share_percent"],
            100.0,
        )

    def test_detects_repair_proxy_and_fails_closed_on_missing_blocker(self):
        raw = [
            run(
                10,
                pr=20,
                name="Required A",
                sha="sha-old",
                created="2026-09-22T15:01:00Z",
                updated="2026-09-22T15:02:00Z",
                conclusion="failure",
            ),
            run(
                11,
                pr=20,
                name="Required B",
                sha="sha-old",
                created="2026-09-22T15:01:00Z",
                updated="2026-09-22T15:02:00Z",
            ),
            run(
                12,
                pr=20,
                name="Required A",
                sha="sha-new",
                created="2026-09-22T15:20:00Z",
                updated="2026-09-22T15:21:00Z",
            ),
            run(
                13,
                pr=20,
                name="Required B",
                sha="sha-new",
                created="2026-09-22T15:20:00Z",
                updated="2026-09-22T15:22:00Z",
            ),
            run(
                14,
                pr=21,
                name="Required A",
                sha="sha-incomplete",
                created="2026-09-22T15:30:00Z",
                updated="2026-09-22T15:31:00Z",
            ),
        ]
        result = build_pr_efficiency(
            raw,
            blocking_workflows=BLOCKING,
            start_at=START,
            end_at=END,
        )
        by_pr = {item["pr_number"]: item for item in result["prs"]}

        self.assertTrue(by_pr[20]["ci_fix_commit_proxy"])
        self.assertTrue(by_pr[20]["latest_head_green"])
        self.assertFalse(by_pr[21]["latest_head_blockers_complete"])
        self.assertFalse(by_pr[21]["latest_head_green"])
        self.assertIsNone(by_pr[21]["latest_head_time_to_green_seconds"])
        self.assertEqual(result["ci_fix_commit_proxy_prs"], 1)
        self.assertEqual(result["ci_fix_commit_proxy_percent"], 50.0)

    def test_excludes_push_and_outside_window(self):
        raw = [
            run(
                30,
                pr=30,
                name="Required A",
                sha="sha-push",
                created="2026-09-22T15:10:00Z",
                updated="2026-09-22T15:11:00Z",
                event="push",
            ),
            run(
                31,
                pr=31,
                name="Required A",
                sha="sha-old",
                created="2026-09-22T14:59:00Z",
                updated="2026-09-22T15:01:00Z",
            ),
        ]
        result = build_pr_efficiency(
            raw,
            blocking_workflows=BLOCKING,
            start_at=START,
            end_at=END,
        )
        self.assertFalse(result["available"])
        self.assertEqual(result["sample_prs"], 0)

    def test_enrichment_is_idempotent_and_registry_is_validated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            analytics = root / "analytics.json"
            markdown = root / "analytics.md"
            registry = root / "registry.json"
            analytics.write_text(
                json.dumps({"collection_window": {"start_at": START.isoformat(), "end_at": END.isoformat()}}),
                encoding="utf-8",
            )
            markdown.write_text("# CI\n", encoding="utf-8")
            registry.write_text(
                json.dumps({"canonical_pr_path": {"blocking": BLOCKING}}),
                encoding="utf-8",
            )
            self.assertEqual(load_blocking_workflows(registry), BLOCKING)

            metrics = build_pr_efficiency(
                [],
                blocking_workflows=BLOCKING,
                start_at=START,
                end_at=END,
            )
            enrich_files(analytics, markdown, metrics)
            enrich_files(analytics, markdown, metrics)

            payload = json.loads(analytics.read_text(encoding="utf-8"))
            self.assertIn("pr_efficiency", payload)
            self.assertEqual(markdown.read_text(encoding="utf-8").count(SECTION_MARKER), 1)


if __name__ == "__main__":
    unittest.main()
