#!/usr/bin/env python3
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_ci_fixed_window_analytics import (  # noqa: E402
    POLICY_ID,
    build_fixed_window_summary,
    fetch_runs_for_window,
    fixed_window_bounds,
    render_fixed_markdown,
)


def run(idx: int, created: str, *, status="completed", conclusion="success"):
    return {
        "id": idx,
        "name": "CI",
        "event": "push",
        "status": status,
        "conclusion": conclusion if status == "completed" else None,
        "head_branch": "main",
        "head_sha": f"sha-{idx}",
        "html_url": f"https://example.test/{idx}",
        "created_at": created,
        "run_started_at": created,
        "updated_at": created,
        "run_attempt": 1,
    }


class FixedWindowAnalyticsTests(unittest.TestCase):
    def test_anchor_is_stable_when_runner_starts_late(self):
        a = fixed_window_bounds(datetime(2026, 9, 5, 15, 45, tzinfo=timezone.utc))
        b = fixed_window_bounds(datetime(2026, 9, 5, 15, 58, tzinfo=timezone.utc))
        self.assertEqual(a, b)
        self.assertEqual(a[0].minute, 40)
        self.assertEqual(a[1].minute, 40)
        self.assertEqual((a[1] - a[0]).total_seconds(), 3600)

    def test_settlement_uses_previous_anchor_before_maturity(self):
        start, end = fixed_window_bounds(datetime(2026, 9, 5, 15, 44, tzinfo=timezone.utc))
        self.assertEqual(end.isoformat(), "2026-09-05T14:40:00+00:00")
        self.assertEqual(start.isoformat(), "2026-09-05T13:40:00+00:00")

    def test_filters_cohort_and_marks_eligible(self):
        raw = [run(i, f"2026-09-05T15:{10 + i:02d}:00Z") for i in range(30)]
        raw += [run(99, "2026-09-05T14:39:59Z"), run(100, "2026-09-05T15:40:00Z")]
        summary = build_fixed_window_summary(
            raw,
            repository="owner/repo",
            as_of=datetime(2026, 9, 5, 15, 45, tzinfo=timezone.utc),
            min_completed_runs=30,
        )
        window = summary["collection_window"]
        self.assertEqual(window["policy_id"], POLICY_ID)
        self.assertEqual(window["runs_in_window"], 30)
        self.assertEqual(window["completed_runs"], 30)
        self.assertEqual(window["completion_coverage_percent"], 100.0)
        self.assertTrue(window["sample_eligible"])
        self.assertEqual(summary["throughput"]["window_span_hours"], 1.0)

    def test_rejects_sparse_or_incomplete_sample(self):
        raw = [run(i, f"2026-09-05T15:{10 + i:02d}:00Z") for i in range(20)]
        raw += [run(100 + i, f"2026-09-05T15:{30 + i:02d}:00Z", status="in_progress") for i in range(5)]
        summary = build_fixed_window_summary(
            raw,
            repository="owner/repo",
            as_of=datetime(2026, 9, 5, 15, 45, tzinfo=timezone.utc),
            min_completed_runs=30,
            min_completion_coverage_percent=90,
            collection_complete=False,
        )
        reasons = summary["collection_window"]["eligibility_reason_codes"]
        self.assertIn("collection_incomplete", reasons)
        self.assertIn("completed_runs_below_minimum", reasons)
        self.assertIn("completion_coverage_below_minimum", reasons)
        self.assertFalse(summary["collection_window"]["sample_eligible"])

    def test_paginates_until_window_start_is_covered(self):
        calls = []
        pages = {
            1: [run(1, "2026-09-05T15:30:00Z")],
            2: [run(2, "2026-09-05T14:30:00Z")],
        }
        def api(path, token):
            calls.append(path)
            page = int(path.rsplit("page=", 1)[1])
            return {"workflow_runs": pages.get(page, [])}
        rows, meta = fetch_runs_for_window(
            "owner", "repo", "t",
            start_at=datetime(2026, 9, 5, 14, 40, tzinfo=timezone.utc),
            max_pages=5,
            per_page=1,
            api_get=api,
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(calls), 2)
        self.assertTrue(meta["collection_complete"])

    def test_markdown_exposes_fixed_window_policy(self):
        raw = [run(i, f"2026-09-05T15:{10 + i:02d}:00Z") for i in range(30)]
        summary = build_fixed_window_summary(
            raw,
            repository="owner/repo",
            as_of=datetime(2026, 9, 5, 15, 45, tzinfo=timezone.utc),
        )
        text = render_fixed_markdown(summary)
        self.assertIn("Janela fixa de coleta", text)
        self.assertIn(POLICY_ID, text)
        self.assertIn("Amostra elegível", text)


if __name__ == "__main__":
    unittest.main()
