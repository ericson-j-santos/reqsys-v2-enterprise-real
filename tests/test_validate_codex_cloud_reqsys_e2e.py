from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_codex_cloud_reqsys_e2e.py"
SPEC = importlib.util.spec_from_file_location("validate_codex_cloud_reqsys_e2e", SCRIPT)
assert SPEC and SPEC.loader
e2e = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(e2e)


class CodexCloudReqSysE2ETests(unittest.TestCase):
    def test_reusable_gateway_accepts_expected_dev_health(self) -> None:
        e2e._validate_reusable_gateway_health(
            {
                "status": "ok",
                "service": "reqsys-ollama-local-gateway",
                "env": "dev",
                "auth_required": False,
            }
        )

    def test_reusable_gateway_rejects_wrong_service(self) -> None:
        with self.assertRaises(e2e.E2EError):
            e2e._validate_reusable_gateway_health(
                {
                    "status": "ok",
                    "service": "other-service",
                    "env": "dev",
                    "auth_required": False,
                }
            )

    def test_reusable_gateway_rejects_production(self) -> None:
        with self.assertRaises(e2e.E2EError):
            e2e._validate_reusable_gateway_health(
                {
                    "status": "ok",
                    "service": "reqsys-ollama-local-gateway",
                    "env": "prod",
                    "auth_required": False,
                }
            )

    def test_reusable_gateway_rejects_auth_required(self) -> None:
        with self.assertRaises(e2e.E2EError):
            e2e._validate_reusable_gateway_health(
                {
                    "status": "ok",
                    "service": "reqsys-ollama-local-gateway",
                    "env": "dev",
                    "auth_required": True,
                }
            )

    def test_stack_env_uses_explicit_gateway_url(self) -> None:
        profile = {
            "CODEX_OLLAMA_MODEL": "gemma4:31b-cloud",
            "CODEX_OLLAMA_GATEWAY_MODEL": "gemma4:31b-cloud",
            "CODEX_OLLAMA_FALLBACK_MODEL": "gemma4:26b-q8-code",
            "CODEX_OLLAMA_BASE_URL": "http://127.0.0.1:11434",
        }
        env = e2e._stack_env(
            profile,
            Path("e2e.db"),
            gateway_url="http://127.0.0.1:18008",
        )
        self.assertEqual(env["CODEX_OLLAMA_GATEWAY_URL"], "http://127.0.0.1:18008")

    def test_validate_port_rejects_invalid_range(self) -> None:
        with self.assertRaises(e2e.E2EError):
            e2e._validate_port(0, name="backend-port")


if __name__ == "__main__":
    unittest.main()
