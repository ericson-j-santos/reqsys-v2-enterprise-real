"""Unit controls for the read-only Noteri worker heartbeat probe."""
from __future__ import annotations

import copy
import json
import unittest

from scripts import noteri_worker_heartbeat_probe as m

SHA = "eb87fe3a9a8f252abc74fe165c55fb6a14964c15"
CID = "study-verify-20261009"


def record(ts="2026-10-09T15:00:00+00:00", **overrides):
    worker = {
        "worker_id": "noteri", "device_name": "Noteri", "profile": "ESTUDO",
        "fresh": True, "controller_online": True, "auth_valid": True,
        "last_heartbeat": ts,
        "capabilities": {"safe_task_types": ["host.profile.set.v1"]},
    }
    worker.update(overrides)
    return {"workers": [worker]}


class TestNoteriWorkerHeartbeatProbe(unittest.TestCase):
    def run_samples(self, samples, **options):
        stream = iter(samples)
        return m.check(
            expected_sha=SHA, correlation_id=CID, host="Noteri",
            get_sha=lambda _: SHA, fetch=lambda: next(stream),
            sleep=lambda _: None, **options,
        )

    def assert_blocked(self, message, operation):
        with self.assertRaises(m.ProbeBlocked) as error:
            operation()
        self.assertEqual(str(error.exception), message)

    def test_positive_two_independent_heartbeats(self):
        result = self.run_samples([
            record(), record("2026-10-09T15:00:25+00:00"),
        ])
        self.assertEqual(
            (result["read_only"], result["heartbeat_advanced"], result["profile"]),
            (True, True, "ESTUDO"),
        )
        self.assertEqual(result["observed_sha"], SHA)

    def test_repeat_is_read_only_and_idempotent(self):
        records = [record(), record("2026-10-09T15:00:25+00:00")]
        before = json.dumps(records, sort_keys=True)
        for _ in range(2):
            self.assertTrue(self.run_samples(records)["ok"])
        self.assertEqual(json.dumps(records, sort_keys=True), before)

    def test_stale(self):
        self.assert_blocked(
            "noteri_worker_not_operational",
            lambda: self.run_samples([record(fresh=False)]),
        )

    def test_offline(self):
        self.assert_blocked(
            "noteri_worker_not_operational",
            lambda: self.run_samples([record(controller_online=False)]),
        )

    def test_invalid_auth(self):
        self.assert_blocked(
            "noteri_worker_not_operational",
            lambda: self.run_samples([record(auth_valid=False)]),
        )

    def test_duplicate_not_accepted(self):
        duplicate = record()
        duplicate["workers"].append(copy.deepcopy(duplicate["workers"][0]))
        self.assert_blocked(
            "noteri_worker_ambiguous_or_missing",
            lambda: self.run_samples([duplicate]),
        )

    def test_worker_missing(self):
        self.assert_blocked(
            "noteri_worker_ambiguous_or_missing",
            lambda: self.run_samples([{"workers": []}]),
        )

    def test_missing_capability(self):
        self.assert_blocked(
            "noteri_profile_capability_missing",
            lambda: self.run_samples([record(capabilities={"safe_task_types": []})]),
        )

    def test_timestamp_no_advancement(self):
        self.assert_blocked(
            "noteri_heartbeat_not_advanced",
            lambda: self.run_samples([record(), record()]),
        )

    def test_timestamp_without_timezone(self):
        self.assert_blocked(
            "noteri_heartbeat_timezone_missing",
            lambda: self.run_samples([record(ts="2026-10-09T15:00:00")]),
        )

    def test_mismatched_sha_no_network(self):
        self.assert_blocked(
            "source_sha_mismatch",
            lambda: m.check(
                expected_sha=SHA, correlation_id=CID, host="Noteri",
                get_sha=lambda _: "f" * 40,
                fetch=lambda: self.fail("network must not be called"),
            ),
        )

    def test_wrong_host_no_network(self):
        self.assert_blocked(
            "host_mismatch",
            lambda: m.check(
                expected_sha=SHA, correlation_id=CID, host="OTHER",
                fetch=lambda: self.fail("network must not be called"),
            ),
        )

    def test_invalid_interval_no_network(self):
        self.assert_blocked(
            "interval_invalid",
            lambda: self.run_samples([], interval_seconds=1),
        )

    def test_invalid_correlation_no_network(self):
        self.assert_blocked(
            "correlation_id_invalid",
            lambda: m.check(
                expected_sha=SHA, correlation_id="x", host="Noteri",
                fetch=lambda: self.fail("network must not be called"),
            ),
        )

    def test_invalid_profile(self):
        self.assert_blocked(
            "noteri_profile_invalid",
            lambda: self.run_samples([record(profile="UNKNOWN")]),
        )

    def test_nonlist_registry(self):
        self.assert_blocked(
            "worker_list_invalid",
            lambda: self.run_samples([{"workers": "invalid"}]),
        )


    def test_governed_workflow_emits_sanitized_failure_classification(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/noteri-control-plane-probe.yml").read_text(encoding="utf-8")
        self.assertIn("HEARTBEAT_NOT_PROVED:$failureReason", workflow)
        self.assertIn("'^[a-z][a-z0-9_]{0,79}
    unittest.main()
", workflow)
        self.assertNotIn("Write-Host $failureReceipt", workflow)


if __name__ == "__main__":
    unittest.main()
