#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
DEFAULT_CONFIG = Path("governance/tooling/command-gateway-session-launcher.json")


def parse_version(value: object) -> tuple[int, int, int]:
    match = VERSION_RE.fullmatch(str(value))
    if not match:
        raise ValueError(f"versão semântica inválida: {value}")
    return tuple(int(part) for part in match.groups())


def validate_contract(data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("schema_version deve ser 1")
    if data.get("tool") != "chatgpt-command-gateway":
        errors.append("tool inválido")
    try:
        if parse_version(data.get("minimum_rules_version")) < (1, 6, 0):
            errors.append("minimum_rules_version deve ser >= 1.6.0")
    except ValueError as exc:
        errors.append(str(exc))
    expected = {
        "required_entrypoint": "session_launcher.py",
        "required_result": "SESSION_LAUNCH_OK",
        "require_expected_head": True,
        "require_materialized_worktree": True,
        "require_state_validated": True,
        "forbid_direct_terminal": True,
        "scope": "chatgpt-triggered-repository-operations",
    }
    for key, value in expected.items():
        if data.get(key) != value:
            errors.append(f"{key} deve ser {value!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    data = json.loads(args.config.read_text(encoding="utf-8"))
    errors = validate_contract(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"COMMAND_GATEWAY_ADOPTION_BLOCKED errors={len(errors)}")
        return 1
    print("COMMAND_GATEWAY_ADOPTION_OK minimum_rules_version=" + data["minimum_rules_version"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
