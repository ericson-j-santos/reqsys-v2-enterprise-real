"""Regressão: não confundir sucesso/cancelamento/watchdog com entrega."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from scripts.teams_notification_slo_metrics import calculate_metrics


NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


def run(run_id: int, event: str, conclusion: str, *, age: int = 1) -> dict:
    created = NOW - timedelta(days=age)
    return {
        "id": run_id,
        "status": "completed",
        "event": event,
        "conclusion": conclusion,
        "created_at": created.isoformat(),
        "run_started_at": created.isoformat(),
        "updated_at": (created + timedelta(seconds=5)).isoformat(),
    }


def metrics(*pages: list[dict]) -> dict:
    return calculate_metrics(
        [{"workflow_runs": page} for page in pages],
        now=NOW,
        window_days=30,
        target_percent=99.0,
    )


class TeamsSloMetricsTest(unittest.TestCase):
    def test_schedule_watchdog_is_not_delivery(self) -> None:
        result = metrics([run(1, "schedule", "failure")])
        self.assertEqual(result["total_runs"], 0)
        self.assertEqual(result["locator_watch"]["non_successful_runs"], 1)
        self.assertEqual(result["state"], "insufficient_data")
        self.assertFalse(result["delivery_verified"])

    def test_successful_push_is_only_execution_proxy(self) -> None:
        result = metrics([run(2, "push", "success")])
        self.assertEqual(result["workflow_execution_state"], "healthy")
        self.assertEqual(result["success_rate_percent"], 100)
        self.assertEqual(result["state"], "unverified_delivery")
        self.assertEqual(result["delivery_state"], "unverified")
        self.assertIsNone(result["delivery_success_rate_percent"])
        self.assertFalse(result["delivery_verified"])

    def test_failure_and_cancelled_are_distinct_and_not_delivery_proofs(self) -> None:
        result = metrics([
            run(3, "workflow_run", "failure"),
            run(4, "workflow_run", "cancelled"),
            run(5, "workflow_run", "skipped"),
            run(6, "schedule", "success"),
            run(7, "workflow_dispatch", "success"),
        ])
        self.assertEqual(result["total_runs"], 3)
        self.assertEqual(result["workflow_execution_errors"], 1)
        self.assertEqual(result["workflow_conclusions"]["cancelled"], 1)
        self.assertEqual(result["workflow_conclusions"]["skipped"], 1)
        self.assertEqual(result["excluded_non_candidate_runs"], 2)
        self.assertEqual(result["remaining_error_budget"], -3)

    def test_pagination_duplicates_are_deduplicated_and_old_runs_ignored(self) -> None:
        first = run(8, "push", "failure")
        updated = {**first, "conclusion": "success", "run_attempt": 2}
        result = metrics([first, run(9, "push", "failure", age=31)], [updated])
        self.assertEqual(result["total_runs"], 1)
        self.assertEqual(result["successful_runs"], 1)

    def test_invalid_page_or_time_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid_github_page"):
            calculate_metrics([{"bad_page": []}], now=NOW, window_days=30, target_percent=99)
        with self.assertRaisesRegex(ValueError, "invalid_slo_parameters"):
            calculate_metrics([], now=NOW, window_days=0, target_percent=99)
        with self.assertRaisesRegex(ValueError, "run_timestamp_without_timezone"):
            wrong = run(10, "push", "success")
            wrong["created_at"] = "2026-10-26T11:00:00"
            metrics([wrong])


if __name__ == "__main__":
    unittest.main()
