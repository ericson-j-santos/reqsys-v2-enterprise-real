from __future__ import annotations

import json
from pathlib import Path

from scripts.check_command_gateway_session_launcher import validate_contract

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "governance" / "tooling" / "command-gateway-session-launcher.json"


def load_contract() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_canonical_contract_is_valid() -> None:
    assert validate_contract(load_contract()) == []


def test_contract_blocks_version_regression() -> None:
    data = load_contract()
    data["minimum_rules_version"] = "1.5.2"
    assert "minimum_rules_version deve ser >= 1.6.0" in validate_contract(data)


def test_contract_blocks_direct_terminal_relaxation() -> None:
    data = load_contract()
    data["forbid_direct_terminal"] = False
    assert any("forbid_direct_terminal" in item for item in validate_contract(data))
