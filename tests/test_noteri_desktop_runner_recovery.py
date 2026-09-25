from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "noteri_desktop_runner_recovery.py"
SPEC = importlib.util.spec_from_file_location("noteri_desktop_runner_recovery", SCRIPT)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def worker_payload(*, contract=1, tasks=None):
    tasks = tasks or sorted(m.BASE_REQUIRED_TASKS)
    return {
        "worker_id": m.WORKER_ID,
        "device_name": m.TARGET_HOST,
        "fresh": True,
        "eligible": True,
        "controller_online": True,
        "auth_valid": True,
        "profile": "NORMAL",
        "controller_version": "0.2.53",
        "capabilities": {
            "recovery_contract_version": contract,
            "safe_task_types": tasks,
        },
    }


class NoteriDesktopRunnerRecoveryTests(unittest.TestCase):
    def test_requires_recovery_contract(self):
        responses = iter([
            (200, {"ready": True}),
            (200, {"workers": [worker_payload(contract=0)]}),
        ])
        with patch.object(m, "request_json", side_effect=lambda *a, **k: next(responses)):
            with self.assertRaisesRegex(m.BridgeError, "recovery_contract_mismatch"):
                m.read_worker()

    def test_requires_all_base_capabilities(self):
        responses = iter([
            (200, {"ready": True}),
            (200, {"workers": [worker_payload(tasks=["host.orchestrator.refresh.v1"])]}),
        ])
        with patch.object(m, "request_json", side_effect=lambda *a, **k: next(responses)):
            with self.assertRaisesRegex(m.BridgeError, "recovery_capabilities_missing"):
                m.read_worker()

    def test_submit_task_is_fixed_and_idempotent(self):
        captured = {}

        def fake_request(method, url, payload=None, timeout=5.0):
            captured.update(method=method, url=url, payload=payload)
            return 201, {
                "item": {"id": "item-1"},
                "created": True,
                "replayed": False,
                "dispatch": {"dispatch_id": "dispatch-1"},
            }

        with patch.object(m, "request_json", side_effect=fake_request):
            result = m.submit_task(
                task_type=m.BOOTSTRAP_TASK,
                payload={"target_host": m.TARGET_HOST},
                correlation_id="corr-12345678",
                idempotency_key="fixed-key",
            )
        self.assertEqual(result["item_id"], "item-1")
        self.assertEqual(captured["payload"]["task_type"], m.BOOTSTRAP_TASK)
        self.assertEqual(captured["payload"]["payload"], {"target_host": m.TARGET_HOST})
        self.assertEqual(captured["payload"]["risk"], 2)
        self.assertEqual(captured["payload"]["max_attempts"], 1)
        self.assertEqual(captured["payload"]["idempotency_key"], "fixed-key")

    def test_blocked_result_fails_closed(self):
        with patch.object(
            m,
            "request_json",
            return_value=(
                200,
                {
                    "item": {
                        "id": "item-1",
                        "status": "BLOQUEADO",
                        "last_error": "target not found",
                    }
                },
            ),
        ):
            with self.assertRaisesRegex(m.BridgeError, "terminal_failure"):
                m.wait_terminal("item-1", m.BOOTSTRAP_TASK, 1)

    def test_existing_bootstrap_capability_skips_refresh(self):
        worker = worker_payload(
            tasks=sorted(m.BASE_REQUIRED_TASKS | {m.BOOTSTRAP_TASK})
        )
        with (
            patch.object(m, "read_worker", return_value=worker),
            patch.object(m, "submit_task") as submit,
        ):
            result = m.ensure_bootstrap_capability("corr-existing")
        submit.assert_not_called()
        self.assertFalse(result["refreshed"])

    def test_missing_bootstrap_capability_requests_exact_main_refresh(self):
        before = worker_payload()
        after = worker_payload(
            tasks=sorted(m.BASE_REQUIRED_TASKS | {m.BOOTSTRAP_TASK})
        )
        with (
            patch.object(m, "read_worker", return_value=before),
            patch.object(
                m,
                "submit_task",
                return_value={
                    "item_id": "refresh-1",
                    "created": True,
                    "replayed": False,
                    "dispatch": {},
                },
            ) as submit,
            patch.object(
                m,
                "wait_terminal",
                return_value={
                    "result": {"handler": "host.orchestrator.refresh.v1"}
                },
            ) as wait,
            patch.object(m, "wait_for_capability", return_value=after) as capability,
        ):
            result = m.ensure_bootstrap_capability("corr-refresh")
        submit.assert_called_once_with(
            task_type="host.orchestrator.refresh.v1",
            payload={
                "target_host": m.TARGET_HOST,
                "expected_sha": m.ORCHESTRATOR_SHA,
            },
            correlation_id="corr-refresh-refresh",
            idempotency_key=(
                f"desktop-orchestrator-refresh:{m.TARGET_HOST}:{m.ORCHESTRATOR_SHA}"
            ),
        )
        wait.assert_called_once_with(
            "refresh-1",
            "host.orchestrator.refresh.v1",
            45,
        )
        capability.assert_called_once_with(m.BOOTSTRAP_TASK, 120)
        self.assertTrue(result["refreshed"])

    def test_execute_requires_verified_listener_and_pickup_contract(self):
        before = worker_payload()
        after = worker_payload(
            tasks=sorted(m.BASE_REQUIRED_TASKS | {m.BOOTSTRAP_TASK})
        )
        with (
            patch.object(m, "validate_source_host", return_value="Noteri"),
            patch.object(m, "read_worker", side_effect=[before, after]),
            patch.object(
                m,
                "ensure_bootstrap_capability",
                return_value={
                    "refreshed": True,
                    "refresh_result": {
                        "handler": "host.orchestrator.refresh.v1"
                    },
                },
            ),
            patch.object(
                m,
                "submit_task",
                return_value={
                    "item_id": "bootstrap-1",
                    "created": True,
                    "replayed": False,
                    "dispatch": {},
                },
            ),
            patch.object(
                m,
                "wait_terminal",
                return_value={
                    "result": {
                        "handler": m.BOOTSTRAP_TASK,
                        "local_listener_verified": True,
                        "pickup_required": True,
                        "listener_pid": 4242,
                    }
                },
            ),
        ):
            result = m.execute("corr-execute", 30)
        self.assertTrue(result["ok"])
        self.assertTrue(result["refresh_performed"])
        self.assertEqual(
            result["runner_bootstrap_result"]["listener_pid"],
            4242,
        )


if __name__ == "__main__":
    unittest.main()
