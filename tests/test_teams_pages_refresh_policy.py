"""Regressão de autorização, limiares, falha fechada e idempotência."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.teams_pages_refresh_policy import assess

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 3, 21, 0, tzinfo=timezone.utc)


def evidence(age: object = 0.4) -> dict[str, object]:
    return {
        "schema_version": "1.1.0",
        "checked_at": (NOW - timedelta(minutes=2)).isoformat(),
        "state": "healthy",
        "http_status": 200,
        "errors": [],
        "data_age_hours": age,
    }


class TeamsPagesRefreshPolicyTests(unittest.TestCase):
    def test_fresh_below_24_hours_never_deploys(self):
        decision = assess(evidence(23.99), now=NOW)
        self.assertEqual(decision["status"], "fresh")
        self.assertFalse(decision["authorized_to_deploy"])
        self.assertFalse(decision["dispatch_performed"])

    def test_boundary_24_hours_requests_owner_and_not_deploy(self):
        decision = assess(evidence(24), now=NOW)
        self.assertEqual(decision["status"], "renewal_required")
        self.assertEqual(decision["owner_action_issue"], 1705)
        self.assertFalse(decision["authorized_to_deploy"])

    def test_boundary_48_hours_still_requires_approval(self):
        self.assertEqual(assess(evidence(48), now=NOW)["status"], "renewal_required")

    def test_expired_public_data_blocks(self):
        self.assertEqual(assess(evidence(48.01), now=NOW)["status"], "blocked")

    def test_unhealthy_monitor_does_not_authorize_renewal(self):
        x = evidence(26)
        x["state"] = "unhealthy"
        self.assertEqual(assess(x, now=NOW)["status"], "blocked")

    def test_unexpected_http_or_error_blocks(self):
        for key, value in (("http_status", 503), ("errors", ["schema invalid"])):
            with self.subTest(key=key):
                x = evidence(26)
                x[key] = value
                self.assertEqual(assess(x, now=NOW)["status"], "blocked")

    def test_invalid_age_values_block(self):
        for age in (None, True, float("nan"), float("inf"), -1, "25"):
            with self.subTest(age=age):
                self.assertEqual(assess(evidence(age), now=NOW)["status"], "blocked")

    def test_absent_or_untrusted_evidence_blocks(self):
        for x in (None, {}, [], "success"):
            with self.subTest(evidence=x):
                self.assertEqual(assess(x, now=NOW)["status"], "blocked")

    def test_stale_or_future_monitor_evidence_blocks(self):
        for delta in (timedelta(minutes=16), timedelta(minutes=-1)):
            x = evidence(26)
            x["checked_at"] = (NOW - delta).isoformat()
            self.assertEqual(assess(x, now=NOW)["status"], "blocked")

    def test_naive_timestamp_blocks(self):
        x = evidence(26)
        x["checked_at"] = "2026-11-03T20:58:00"
        self.assertEqual(assess(x, now=NOW)["status"], "blocked")

    def test_same_input_is_idempotent(self):
        x = evidence(26)
        self.assertEqual(assess(x, now=NOW), assess(x, now=NOW))

    def test_workflow_preserves_single_writer_and_owner_dispatch(self):
        w = (ROOT / ".github/workflows/teams-dashboard-availability-monitor.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/teams_pages_refresh_policy.py", w)
        self.assertIn("renewal_required", w)
        self.assertIn("/reqsys run deploy-pages-current-main", w)
        self.assertIn("<!-- reqsys-operational-panel -->", w)
        self.assertIn("if: steps.refresh_policy.outputs.status", w)
        self.assertNotIn("actions/deploy-pages@", w)
        self.assertNotIn("pages: write", w)
        self.assertNotIn("workflow_dispatch_inputs", w)


if __name__ == "__main__":
    unittest.main()
