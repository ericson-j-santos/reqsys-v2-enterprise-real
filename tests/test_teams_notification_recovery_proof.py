"""Exercita o produtor real de evidencia; nao chama GitHub nem Teams."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/teams-notification-observability.yml"


class TeamsNotificationRecoveryProofTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.workflow = yaml.safe_load(cls.text)
        cls.code = cls.workflow["jobs"]["observe"]["steps"][0]["run"]
        cls.code = cls.code.split("python - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]

    def observe(self, event="workflow_run", conclusion="success", run_event="workflow_run", code=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = dict(os.environ)
            env.update(
                EVENT_NAME=event, REPOSITORY="owner/reqsys",
                WORKFLOW_NAME="Teams Commit Notification", RUN_ID="42",
                RUN_URL="https://github.com/owner/reqsys/actions/runs/42",
                RUN_CONCLUSION=conclusion, RUN_EVENT=run_event,
                HEAD_SHA="a" * 40, HEAD_BRANCH="main",
                GITHUB_OUTPUT=str(root / "output"),
            )
            result = subprocess.run(
                [sys.executable, "-c", self.code if code is None else code],
                cwd=root, env=env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads((root / "evidence/teams-notification-delivery.json").read_text())
            return payload, (root / "output").read_text()

    def assert_unverified(self, payload):
        self.assertIs(payload["healthy"], False)
        self.assertIs(payload["delivery_verified"], False)

    def test_success_is_observed_but_does_not_prove_delivery(self):
        payload, output = self.observe()
        self.assertTrue(payload["workflow_succeeded"])
        self.assertEqual(payload["delivery_state"], "unverified")
        self.assertEqual(payload["run_id"], "42")
        self.assertEqual(payload["head_sha"], "a" * 40)
        self.assertIn("healthy=false", output)
        self.assert_unverified(payload)

    def test_failure_stays_visible(self):
        payload, output = self.observe(conclusion="failure")
        self.assertEqual(payload["delivery_state"], "failed")
        self.assertFalse(payload["workflow_succeeded"])
        self.assertIn("conclusion=failure", output)
        self.assert_unverified(payload)
        step = next(s for s in self.workflow["jobs"]["observe"]["steps"]
                    if s["name"] == "Abrir ou atualizar incidente")
        self.assertEqual(step["if"], "steps.evidence.outputs.conclusion == 'failure'")

    def test_skipped_cancelled_and_unknown_never_prove_recovery(self):
        for conclusion in ("skipped", "cancelled", "unknown", ""):
            with self.subTest(conclusion=conclusion):
                payload, _ = self.observe(conclusion=conclusion)
                self.assert_unverified(payload)
                self.assertFalse(payload["workflow_succeeded"])

    def test_manual_and_locator_watch_are_not_delivery_tests(self):
        payload, _ = self.observe(event="workflow_dispatch")
        self.assertEqual(payload["delivery_state"], "not_evaluated")
        self.assert_unverified(payload)
        for conclusion in ("success", "failure"):
            payload, _ = self.observe(run_event="schedule", conclusion=conclusion)
            self.assertEqual(payload["delivery_state"], "locator_watch")
            self.assert_unverified(payload)

    def test_replay_has_same_decision_and_no_external_mutation(self):
        first, _ = self.observe()
        second, _ = self.observe()
        first.pop("observed_at_utc")
        second.pop("observed_at_utc")
        self.assertEqual(first, second)
        self.assertNotIn("gh issue close", self.text)
        self.assertNotIn("Recuperação confirmada automaticamente", self.text)
        self.assertNotIn("urllib", self.code)
        self.assertNotIn("subprocess", self.code)

    def test_negative_control_reproduces_old_false_positive_then_restores(self):
        legacy = self.code.replace(
            '"healthy": False,',
            '"healthy": conclusion in {"success", "manual_validation"},',
        )
        self.assertNotEqual(legacy, self.code)
        payload, _ = self.observe(code=legacy)
        with self.assertRaises(AssertionError):
            self.assert_unverified(payload)
        restored, _ = self.observe()
        self.assert_unverified(restored)


if __name__ == "__main__":
    unittest.main()
