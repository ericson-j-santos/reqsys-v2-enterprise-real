from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ci_health_regression_monitor.py"
WORKFLOW = ROOT / ".github" / "workflows" / "ci-lead-time-analytics.yml"

SPEC = importlib.util.spec_from_file_location("ci_health_regression_monitor", SCRIPT)
assert SPEC and SPEC.loader
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)

NOW = datetime(2026, 9, 29, 22, 0, tzinfo=timezone.utc)
BLOCKING = ["CI", "Governance"]
SOURCE_SHA = "a" * 40


def run(
    run_id: int,
    *,
    pr: int | None,
    name: str,
    sha: str,
    created: datetime,
    duration_seconds: int = 60,
    conclusion: str = "success",
    attempt: int = 1,
    event: str = "pull_request",
):
    return {
        "id": run_id,
        "name": name,
        "event": event,
        "status": "completed",
        "conclusion": conclusion,
        "head_sha": sha,
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "updated_at": (created + timedelta(seconds=duration_seconds)).isoformat().replace("+00:00", "Z"),
        "run_attempt": attempt,
        "html_url": f"https://github.test/actions/runs/{run_id}",
        "pull_requests": ([{"number": pr}] if pr is not None else []),
    }


def pull(
    number: int,
    *,
    state: str,
    head_sha: str,
    updated: datetime,
    merged_at: datetime | None = None,
    merge_sha: str | None = None,
):
    return {
        "number": number,
        "state": state,
        "updated_at": updated.isoformat().replace("+00:00", "Z"),
        "merged_at": (
            merged_at.isoformat().replace("+00:00", "Z")
            if merged_at is not None
            else None
        ),
        "merge_commit_sha": merge_sha,
        "head": {"sha": head_sha},
    }


class CiHealthRegressionMonitorTests(unittest.TestCase):
    def analyze(self, runs, pulls):
        return monitor.analyze(
            runs,
            pulls,
            blocking_workflows=BLOCKING,
            now=NOW,
            source_sha=SOURCE_SHA,
        )

    def test_time_to_first_failure_material_regression(self):
        rows = []
        for idx in range(3):
            created = NOW - timedelta(days=10, minutes=idx)
            rows.append(
                run(
                    10 + idx,
                    pr=10 + idx,
                    name="CI",
                    sha=f"base-{idx}",
                    created=created,
                    duration_seconds=60,
                    conclusion="failure",
                )
            )
        for idx in range(3):
            created = NOW - timedelta(days=2, minutes=idx)
            rows.append(
                run(
                    20 + idx,
                    pr=20 + idx,
                    name="CI",
                    sha=f"current-{idx}",
                    created=created,
                    duration_seconds=300,
                    conclusion="failure",
                )
            )
        report = self.analyze(rows, [])
        metrics = {item["metric"] for item in report["alerts"]}
        self.assertIn("time_to_first_failure", metrics)
        self.assertTrue(report["material_regression"])

    def test_rerun_without_change_material_regression(self):
        rows = []
        base = NOW - timedelta(days=10)
        current = NOW - timedelta(days=2)
        for idx in range(20):
            rows.append(
                run(
                    100 + idx,
                    pr=100 + idx,
                    name="Other",
                    sha=f"b-{idx}",
                    created=base + timedelta(minutes=idx),
                    attempt=2 if idx == 0 else 1,
                )
            )
        for idx in range(20):
            rows.append(
                run(
                    200 + idx,
                    pr=200 + idx,
                    name="Other",
                    sha=f"c-{idx}",
                    created=current + timedelta(minutes=idx),
                    attempt=2 if idx < 4 else 1,
                )
            )
        report = self.analyze(rows, [])
        metrics = {item["metric"] for item in report["alerts"]}
        self.assertIn("reruns_without_change", metrics)

    def test_post_merge_false_green_is_detected_on_exact_merge_sha(self):
        head = "head-green"
        merge = "merge-failed"
        created = NOW - timedelta(days=1, hours=2)
        rows = [
            run(301, pr=301, name="CI", sha=head, created=created),
            run(302, pr=301, name="Governance", sha=head, created=created),
            run(
                303,
                pr=None,
                name="Main Post-Merge Validation",
                sha=merge,
                created=NOW - timedelta(days=1),
                conclusion="failure",
                event="push",
            ),
        ]
        pulls = [
            pull(
                301,
                state="closed",
                head_sha=head,
                updated=NOW - timedelta(days=1),
                merged_at=NOW - timedelta(days=1, hours=1),
                merge_sha=merge,
            )
        ]
        report = self.analyze(rows, pulls)
        alert = next(item for item in report["alerts"] if item["metric"] == "post_merge_false_green")
        self.assertEqual(alert["evidence"][0]["merge_sha"], merge)
        self.assertEqual(alert["evidence"][0]["failed_runs"][0]["head_sha"], merge)

    def test_sha_divergence_requires_current_head_and_stale_green_head(self):
        stale = "stale-green"
        current = "current-head"
        created = NOW - timedelta(days=1)
        rows = [
            run(401, pr=401, name="CI", sha=stale, created=created),
            run(402, pr=401, name="Governance", sha=stale, created=created),
            run(403, pr=401, name="CI", sha=current, created=created + timedelta(hours=1)),
        ]
        pulls = [
            pull(
                401,
                state="open",
                head_sha=current,
                updated=NOW - timedelta(hours=1),
            )
        ]
        report = self.analyze(rows, pulls)
        alert = next(item for item in report["alerts"] if item["metric"] == "sha_divergence")
        evidence = alert["evidence"][0]
        self.assertEqual(evidence["current_head_sha"], current)
        self.assertEqual(evidence["stale_green_head_sha"], stale)

    def test_recent_head_change_does_not_alert_sha_divergence(self):
        stale = "stale-green"
        current = "current-head"
        created = NOW - timedelta(hours=2)
        rows = [
            run(451, pr=451, name="CI", sha=stale, created=created),
            run(452, pr=451, name="Governance", sha=stale, created=created),
        ]
        pulls = [
            pull(
                451,
                state="open",
                head_sha=current,
                updated=NOW - timedelta(minutes=10),
            )
        ]
        report = self.analyze(rows, pulls)
        self.assertNotIn("sha_divergence", {item["metric"] for item in report["alerts"]})

    def test_in_progress_current_head_does_not_alert_sha_divergence(self):
        stale = "stale-green"
        current = "current-head"
        created = NOW - timedelta(hours=2)
        pending = run(
            463,
            pr=461,
            name="CI",
            sha=current,
            created=created + timedelta(minutes=30),
        )
        pending["status"] = "in_progress"
        pending["conclusion"] = None
        rows = [
            run(461, pr=461, name="CI", sha=stale, created=created),
            run(462, pr=461, name="Governance", sha=stale, created=created),
            pending,
        ]
        pulls = [
            pull(
                461,
                state="open",
                head_sha=current,
                updated=NOW - timedelta(hours=1),
            )
        ]
        report = self.analyze(rows, pulls)
        self.assertNotIn("sha_divergence", {item["metric"] for item in report["alerts"]})

    def test_small_variation_does_not_alert(self):
        rows = []
        for idx in range(3):
            rows.append(
                run(
                    500 + idx,
                    pr=500 + idx,
                    name="CI",
                    sha=f"base-{idx}",
                    created=NOW - timedelta(days=10, minutes=idx),
                    duration_seconds=100,
                    conclusion="failure",
                )
            )
            rows.append(
                run(
                    600 + idx,
                    pr=600 + idx,
                    name="CI",
                    sha=f"current-{idx}",
                    created=NOW - timedelta(days=2, minutes=idx),
                    duration_seconds=110,
                    conclusion="failure",
                )
            )
        report = self.analyze(rows, [])
        self.assertFalse(report["material_regression"])
        self.assertEqual(report["alerts"], [])

    def test_workflow_contract_reuses_existing_analytics_and_pins_new_actions(self):
        raw = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cron: '45 * * * *'", raw)
        self.assertIn("pull_request:", raw)
        self.assertIn("scripts/ci_health_regression_monitor.py", raw)
        self.assertIn("tests/test_ci_health_regression_watch.py", raw)
        self.assertIn("issues: write", raw)
        self.assertIn("if: github.event_name != 'pull_request'", raw)
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", raw)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", raw)
        self.assertIn("actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093", raw)
        self.assertIn("actions/github-script@f28e40c7f34bde8b3046d885e986cb6290c5673b", raw)
        self.assertIn("reqsys-ci-health-regression-watch", raw)


if __name__ == "__main__":
    unittest.main()
