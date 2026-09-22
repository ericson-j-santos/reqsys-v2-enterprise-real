#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ENV_PATTERN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("registro de terceiros deve ser um objeto YAML")
    return payload


def load_env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ENV_PATTERN.match(line)
        if match:
            keys.add(match.group(1))
    return keys


def build_report(register_path: Path, env_path: Path) -> dict[str, Any]:
    register = load_yaml(register_path)
    providers = register.get("providers") or []
    if not isinstance(providers, list):
        raise ValueError("providers deve ser uma lista")

    env_keys = load_env_keys(env_path)
    provider_ids: set[str] = set()
    duplicate_provider_ids: list[str] = []
    missing_config_source: list[str] = []
    invalid_config_keys: dict[str, list[str]] = {}
    missing_env_keys: dict[str, list[str]] = {}
    referenced_keys: set[str] = set()

    for index, provider in enumerate(providers):
        if not isinstance(provider, dict):
            missing_config_source.append(f"index:{index}")
            continue

        provider_id = str(provider.get("id") or f"index:{index}")
        if provider_id in provider_ids:
            duplicate_provider_ids.append(provider_id)
        provider_ids.add(provider_id)

        config_source = provider.get("config_source")
        if not isinstance(config_source, list) or not config_source:
            missing_config_source.append(provider_id)
            continue

        invalid: list[str] = []
        absent: list[str] = []
        for value in config_source:
            key = str(value)
            referenced_keys.add(key)
            if not KEY_PATTERN.fullmatch(key):
                invalid.append(key)
            elif key not in env_keys:
                absent.append(key)
        if invalid:
            invalid_config_keys[provider_id] = sorted(set(invalid))
        if absent:
            missing_env_keys[provider_id] = sorted(set(absent))

    structural_errors = bool(
        duplicate_provider_ids
        or missing_config_source
        or invalid_config_keys
        or missing_env_keys
    )
    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-05",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "source_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "env_source_sha256": hashlib.sha256(env_path.read_bytes()).hexdigest(),
        "summary": {
            "provider_count": len(providers),
            "declared_env_keys": len(env_keys),
            "referenced_config_keys": len(referenced_keys),
            "providers_with_missing_config_source": len(missing_config_source),
            "providers_with_invalid_config_keys": len(invalid_config_keys),
            "providers_with_missing_env_keys": len(missing_env_keys),
        },
        "duplicate_provider_ids": sorted(set(duplicate_provider_ids)),
        "missing_config_source_provider_ids": sorted(missing_config_source),
        "invalid_config_keys": invalid_config_keys,
        "missing_env_keys": missing_env_keys,
        "result": "invalid" if structural_errors else "valid",
        "automatic_blocking": structural_errors,
        "production_touched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", required=True, type=Path)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report = build_report(args.register, args.env_file)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if report["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
