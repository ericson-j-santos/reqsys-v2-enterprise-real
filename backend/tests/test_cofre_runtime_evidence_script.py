from __future__ import annotations

import importlib.util
import stat
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cofre_runtime_evidence.py"
spec = importlib.util.spec_from_file_location("cofre_runtime_evidence", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def _base_args(tmp_path: Path) -> list[str]:
    return [
        "--phase",
        "before-restart",
        "--base-url",
        "https://example.test",
        "--environment",
        "dev",
        "--admin-jwt",
        "jwt-value",
        "--state-key",
        Fernet.generate_key().decode("ascii"),
        "--correlation-id",
        "corr-1",
        "--state-file",
        str(tmp_path / "state.bin"),
        "--evidence-file",
        str(tmp_path / "evidence.json"),
    ]


def test_build_evidence_never_exposes_sensitive_values(tmp_path: Path):
    args = module.parse_args(_base_args(tmp_path))
    evidence = module.build_evidence(args, {"ok": True, "phase": "before_restart"})
    serialized = str(evidence)
    assert "jwt-value" not in serialized
    assert args.state_key not in serialized
    assert evidence["sensitive_values_exposed"] is False


def test_parse_args_blocks_production(tmp_path: Path):
    args = _base_args(tmp_path)
    args[args.index("dev")] = "prod"
    with pytest.raises(SystemExit):
        module.parse_args(args)


def test_sha256_is_deterministic_and_non_reversible_representation():
    first = module._sha256("secret-value")
    second = module._sha256("secret-value")
    assert first == second
    assert first != "secret-value"
    assert len(first) == 64


def test_transient_state_is_encrypted_and_private(tmp_path: Path):
    state_path = tmp_path / "state.bin"
    state_key = Fernet.generate_key().decode("ascii")
    sensitive = {
        "secret_value": "secret-value",
        "scoped_token": "token-value",
        "token_id": 10,
    }

    module._encrypt_state(state_path, sensitive, state_key)

    raw = state_path.read_bytes()
    assert b"secret-value" not in raw
    assert b"token-value" not in raw
    assert module._decrypt_state(state_path, state_key) == sensitive
    assert stat.S_IMODE(state_path.stat().st_mode) == 0o600


def test_invalid_state_key_is_rejected(tmp_path: Path):
    state_path = tmp_path / "state.bin"
    valid_key = Fernet.generate_key().decode("ascii")
    module._encrypt_state(state_path, {"value": "secret"}, valid_key)

    with pytest.raises(module.GateError):
        module._decrypt_state(state_path, Fernet.generate_key().decode("ascii"))
