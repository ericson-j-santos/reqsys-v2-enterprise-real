from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "configure_codex_ollama_windows.py"
SPEC = importlib.util.spec_from_file_location("configure_codex_ollama_windows", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class ConfigureCodexOllamaWindowsTests(unittest.TestCase):
    def test_validate_model_accepts_cloud_alias(self) -> None:
        self.assertEqual(mod.validate_model("gemma4:31b-cloud"), "gemma4:31b-cloud")

    def test_validate_model_rejects_shell_meta(self) -> None:
        with self.assertRaises(mod.ConfigError):
            mod.validate_model("gemma4:31b-cloud;whoami")

    def test_validate_base_url_accepts_loopback(self) -> None:
        self.assertEqual(
            mod.validate_base_url("http://127.0.0.1:11434/"),
            "http://127.0.0.1:11434",
        )

    def test_validate_base_url_rejects_remote(self) -> None:
        with self.assertRaises(mod.ConfigError):
            mod.validate_base_url("https://ollama.example.com")

    def test_desired_values_aligns_direct_and_gateway(self) -> None:
        values = mod.desired_values("gemma4:31b-cloud", "http://localhost:11434")
        self.assertEqual(values["CODEX_OLLAMA_MODEL"], "gemma4:31b-cloud")
        self.assertEqual(values["CODEX_OLLAMA_GATEWAY_MODEL"], "gemma4:31b-cloud")
        self.assertEqual(values["CODEX_OLLAMA_BASE_URL"], "http://localhost:11434")


if __name__ == "__main__":
    unittest.main()
