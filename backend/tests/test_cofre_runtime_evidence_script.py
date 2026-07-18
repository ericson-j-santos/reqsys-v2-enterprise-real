from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cofre_runtime_evidence.py"
spec = importlib.util.spec_from_file_location("cofre_runtime_evidence", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_build_evidence_never_exposes_sensitive_values():
    args = module.parse_args([
        "--phase", "before-restart",
        "--base-url", "https://example.test",
        "--environment", "dev",
        "--admin-jwt", "jwt-value",
        "--correlation-id", "corr-1",
        "--state-file", "/tmp/state.json",
        "--evidence-file", "/tmp/evidence.json",
    ])
    evidence = module.build_evidence(args, {"ok": True, "phase": "before_restart"})
    serialized = str(evidence)
    assert "jwt-value" not in serialized
    assert evidence["sensitive_values_exposed"] is False


def test_parse_args_blocks_production():
    with pytest.raises(SystemExit):
        module.parse_args([
            "--phase", "before-restart",
            "--base-url", "https://example.test",
            "--environment", "prod",
            "--admin-jwt", "jwt-value",
            "--correlation-id", "corr-1",
            "--state-file", "/tmp/state.json",
            "--evidence-file", "/tmp/evidence.json",
        ])


def test_sha256_is_deterministic_and_non_reversible_representation():
    first = module._sha256("secret-value")
    second = module._sha256("secret-value")
    assert first == second
    assert first != "secret-value"
    assert len(first) == 64
