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
    tasks = tasks or sorted(m.REQUIRED_TASKS)
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

    def test_requires_all_capabilities(self):
        responses = iter([
            (200, {"ready": True}),
            (200, {"workers": [worker_payload(tasks=["host.orchestrator.refresh.v1"])]}),
        ])
        with patch.object(m, "request_json", side_effect=lambda *a, **k: next(responses)):
            with self.assertRaisesRegex(m.BridgeError, "recovery_capabilities_missing"):
                m.read_worker()

    def test_submit_is_fixed_and_idempotent(self):
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
            result = m.submit_runner_recovery("corr-12345678")
        self.assertEqual(result["item_id"], "item-1")
        self.assertEqual(captured["payload"]["task_type"], "host.github_runner.recover.v1")
        self.assertEqual(captured["payload"]["payload"], {"target_host": "DESKTOP-PDQK954"})
        self.assertEqual(captured["payload"]["risk"], 2)
        self.assertEqual(captured["payload"]["max_attempts"], 1)
        self.assertEqual(
            captured["payload"]["idempotency_key"],
            "desktop-runner-recovery:DESKTOP-PDQK954:0.2.53",
        )

    def test_blocked_result_fails_closed(self):
        with patch.object(
            m,
            "request_json",
            return_value=(
                200,
                {"item": {"id": "item-1", "status": "BLOQUEADO", "last_error": "target not found"}},
            ),
        ):
            with self.assertRaisesRegex(m.BridgeError, "terminal_failure"):
                m.wait_terminal("item-1", 1)


if __name__ == "__main__":
    unittest.main()
