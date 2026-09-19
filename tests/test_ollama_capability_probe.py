from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ollama_capability_probe.py"
SPEC = importlib.util.spec_from_file_location("ollama_capability_probe", SCRIPT)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class OllamaCapabilityProbeTests(unittest.TestCase):
    def test_select_model_prioriza_running(self) -> None:
        model, source = probe.select_model(
            None,
            [{"name": "gemma4:31b-cloud"}],
            [{"name": "qwen2.5-coder:7b"}],
            "fallback:7b",
        )
        self.assertEqual(model, "gemma4:31b-cloud")
        self.assertEqual(source, "running")

    def test_select_model_prefere_cloud_31b_quando_nao_ha_running(self) -> None:
        model, source = probe.select_model(
            None,
            [],
            [{"name": "qwen2.5-coder:7b"}, {"name": "gemma4:31b-cloud"}],
            None,
        )
        self.assertEqual(model, "gemma4:31b-cloud")
        self.assertEqual(source, "available_cloud_31b")

    def test_extract_context_combina_ps_e_show(self) -> None:
        result = probe.extract_context_length(
            {
                "model_info": {"gemma.context_length": 262144},
                "parameters": "temperature 0.1\nnum_ctx 131072\n",
            },
            [{"name": "gemma4:31b-cloud", "context_length": 65536}],
            "gemma4:31b-cloud",
        )
        self.assertEqual(result["reported"], 262144)
        self.assertEqual(len(result["sources"]), 3)

    def test_score_code_response_detecta_requisitos(self) -> None:
        scored = probe.score_code_response(
            "Use seen, value.strip().casefold(); preserve order. "
            "pytest: assert normalize_ids([' A ', 'a']) == ['A']"
        )
        self.assertEqual(scored["passed"], scored["total"])

    def test_base_url_remota_bloqueada_por_padrao(self) -> None:
        with self.assertRaises(probe.ProbeError):
            probe._ensure_loopback("https://example.com:11434", False)

    def test_base_url_loopback_permitida(self) -> None:
        self.assertEqual(
            probe._ensure_loopback("http://localhost:11434/", False),
            "http://localhost:11434",
        )


if __name__ == "__main__":
    unittest.main()
