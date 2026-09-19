from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "configure_codex_ollama_windows.py"
SPEC = importlib.util.spec_from_file_location("configure_codex_ollama_windows_fallback", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_desired_values_persiste_primario_e_fallback() -> None:
    values = mod.desired_values(
        "gemma4:31b-cloud",
        "http://127.0.0.1:11434",
        "gemma4:26b-q8-code",
    )
    assert values["CODEX_OLLAMA_MODEL"] == "gemma4:31b-cloud"
    assert values["CODEX_OLLAMA_GATEWAY_MODEL"] == "gemma4:31b-cloud"
    assert values["CODEX_OLLAMA_FALLBACK_MODEL"] == "gemma4:26b-q8-code"
