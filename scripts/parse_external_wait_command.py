#!/usr/bin/env python3
"""Parseia comandos auditáveis para o recorder de espera externa do ReqSys."""
from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path

PREFIX = "/external-wait"
ALLOWED_ACTIONS = {"blocked", "unblocked"}
ALLOWED_CATEGORIES = {
    "human_gate",
    "external_provider",
    "permission_admin",
    "secret_or_credential",
    "infrastructure_external",
}
REQUIRED_KEYS = {"action", "category", "wait_id", "correlation_id"}
OPTIONAL_KEYS = {"sha", "source_reference"}
TOKEN_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,120}$")
SOURCE_RE = re.compile(r"^[A-Za-z0-9._:/#?=-]{1,200}$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")


def parse_command(command: str) -> dict[str, str | None]:
    try:
        parts = shlex.split(command.strip())
    except ValueError as exc:
        raise ValueError(f"command_syntax_invalid:{exc}") from exc
    if not parts or parts[0] != PREFIX:
        raise ValueError("command_prefix_invalid")

    values: dict[str, str] = {}
    allowed = REQUIRED_KEYS | OPTIONAL_KEYS
    for token in parts[1:]:
        if "=" not in token:
            raise ValueError("command_token_invalid")
        key, value = token.split("=", 1)
        if key not in allowed:
            raise ValueError(f"command_key_unknown:{key}")
        if key in values:
            raise ValueError(f"command_key_duplicate:{key}")
        if not value:
            raise ValueError(f"command_value_empty:{key}")
        values[key] = value

    missing = sorted(REQUIRED_KEYS - values.keys())
    if missing:
        raise ValueError("command_required_missing:" + ",".join(missing))
    if values["action"] not in ALLOWED_ACTIONS:
        raise ValueError("action_invalid")
    if values["category"] not in ALLOWED_CATEGORIES:
        raise ValueError("category_invalid")
    if not TOKEN_RE.fullmatch(values["wait_id"]):
        raise ValueError("wait_id_invalid")
    if not TOKEN_RE.fullmatch(values["correlation_id"]):
        raise ValueError("correlation_id_invalid")
    sha = values.get("sha")
    if sha and not SHA_RE.fullmatch(sha):
        raise ValueError("sha_invalid")
    source_reference = values.get("source_reference")
    if source_reference and not SOURCE_RE.fullmatch(source_reference):
        raise ValueError("source_reference_invalid")

    return {
        "action": values["action"],
        "category": values["category"],
        "wait_id": values["wait_id"],
        "correlation_id": values["correlation_id"],
        "sha": sha,
        "source_reference": source_reference,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--command")
    source.add_argument("--command-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    command = args.command if args.command is not None else args.command_file.read_text(encoding="utf-8")
    try:
        payload = parse_command(command)
    except ValueError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    result = {"valid": True, **payload}
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
