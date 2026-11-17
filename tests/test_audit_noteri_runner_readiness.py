"""Bounded, fail-closed Noteri runner checks and CI binding contract."""
import copy
import unittest
from pathlib import Path

from scripts.audit_noteri_runner_readiness import LABELS, RUNNER, ReadinessError, classify

ARGS = dict(source_sha="a" * 40, noteri_sha="b" * 40, run_id="123",
            run_attempt="1", observed_at="2026-11-17T18:00:00Z")


def inventory(status="online", busy=False, labels=None):
    names = LABELS if labels is None else labels
    return [{"total_count": 1, "runners": [{
        "id": 34, "name": RUNNER, "status": status, "busy": busy,
        "os": "Windows", "labels": [{"name": name} for name in names],
    }]}]


class RunnerReadinessTests(unittest.TestCase):
    def test_ready_is_not_authorization(self):
        r = classify(inventory(), **ARGS)
        self.assertEqual(r["state"], "available_at_observation")
        self.assertIs(r["ready_for_dispatch_precheck"], True)
        self.assertIs(r["authorization_for_host"], False)
        self.assertIs(r["dispatch_executed"], False)
        self.assertIs(r["sample_not_lease"], True)

    def test_replay_idempotent(self):
        raw = inventory()
        before = copy.deepcopy(raw)
        self.assertEqual(classify(raw, **ARGS), classify(raw, **ARGS))
        self.assertEqual(raw, before)

    def test_offline_blocks(self):
        r = classify(inventory(status="offline"), **ARGS)
        self.assertEqual(r["state"], "offline")
        self.assertFalse(r["ready_for_dispatch_precheck"])

    def test_busy_blocks(self):
        r = classify(inventory(busy=True), **ARGS)
        self.assertEqual(r["state"], "busy")
        self.assertFalse(r["ready_for_dispatch_precheck"])

    def test_label_drift_blocks(self):
        r = classify(inventory(labels=["self-hosted", "Windows"]), **ARGS)
        self.assertEqual(r["state"], "label_mismatch")
        self.assertIn("noteri", r["missing_required_labels"])

    def test_complete_pagination_accepts(self):
        pages = inventory()
        pages[0]["total_count"] = 2
        pages.append({"total_count": 2, "runners": [{"id": 91, "name": "Other"}]})
        self.assertTrue(classify(pages, **ARGS)["ready_for_dispatch_precheck"])

    def test_partial_ambiguous_invalid_inventory_blocks(self):
        base = inventory()[0]["runners"]
        cases = ([], {}, [{"total_count": 2, "runners": base}],
                 [{"total_count": 0, "runners": base}],
                 [{"total_count": True, "runners": base}],
                 [{"total_count": 1, "runners": ["wrong"]}],
                 [{"total_count": 1, "runners": base},
                  {"total_count": 2, "runners": []}])
        for sample in cases:
            with self.subTest(sample=sample), self.assertRaises(ReadinessError):
                classify(sample, **ARGS)

    def test_duplicate_id_and_duplicate_runner_block(self):
        data = inventory()
        data[0]["total_count"] = 2
        data[0]["runners"].append(copy.deepcopy(data[0]["runners"][0]))
        with self.assertRaises(ReadinessError):
            classify(data, **ARGS)
        data[0]["runners"][1]["id"] = 91
        with self.assertRaises(ReadinessError):
            classify(data, **ARGS)

    def test_wrong_runner_identity_blocks(self):
        data = inventory()
        data[0]["runners"][0]["name"] = "Noteri"
        with self.assertRaises(ReadinessError):
            classify(data, **ARGS)

    def test_invalid_status_busy_os_or_labels_blocks(self):
        for key, value in (("status", "idle"), ("busy", "false"),
                           ("os", "Linux"), ("labels", "invalid"),
                           ("labels", [{"name": "X64"}, {"name": "X64"}])):
            data = inventory()
            data[0]["runners"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ReadinessError):
                classify(data, **ARGS)

    def test_invalid_identity_and_provenance_blocks(self):
        for key, value in (("source_sha", "invalid"), ("noteri_sha", "0"),
                           ("run_id", "-1"), ("run_attempt", "0"),
                           ("observed_at", "yesterday")):
            with self.subTest(key=key), self.assertRaises(ReadinessError):
                classify(inventory(), **{**ARGS, key: value})


class RunnerWorkflowBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (Path(__file__).resolve().parents[1] /
                        ".github/workflows/self-hosted-runner-governance-guard.yml").read_text(encoding="utf-8")
        cls.job = cls.workflow.split("\n  noteri_runner_readiness:\n", 1)[1].split(
            "\n  governance:\n", 1)[0]

    def test_owner_main_and_schedule_or_manual_read_only_mode(self):
        self.assertIn("noteri-runner-readiness", self.workflow)
        self.assertIn("github.event_name == 'schedule'", self.job)
        self.assertIn("inputs.mode == 'noteri-runner-readiness'", self.job)
        self.assertIn("github.ref == 'refs/heads/main'", self.job)
        self.assertIn("github.repository == 'ericson-j-santos/reqsys-v2-enterprise-real'", self.job)

    def test_scoped_token_and_existing_secrets(self):
        self.assertIn("permission-administration: read", self.job)
        self.assertNotIn("permission-administration: write", self.job)
        self.assertIn("vars.REQSYS_STACK_REBASE_APP_ID", self.job)
        self.assertIn("secrets.REQSYS_STACK_REBASE_PRIVATE_KEY", self.job)
        self.assertIn("repositories: noteri-runtime", self.job)

    def test_no_dispatch_or_mutation(self):
        self.assertIn("repos/ericson-j-santos/noteri-runtime/actions/runners?per_page=100", self.job)
        self.assertIn("scripts/audit_noteri_runner_readiness.py", self.job)
        self.assertNotIn("/dispatches", self.job)
        self.assertNotIn("gh workflow run", self.job)
        self.assertNotIn("upload-artifact", self.job)

    def test_api_fail_closed(self):
        self.assertIn("NOTERI_RUNNER_ADMIN_READ_UNAVAILABLE", self.job)
        self.assertIn("--paginate --slurp", self.job)
        self.assertIn("set -euo pipefail", self.job)
