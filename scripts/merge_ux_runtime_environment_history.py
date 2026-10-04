#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

MAX_HISTORY = 90
VALID_ENVIRONMENTS = {"dev", "stg", "prod"}


def merge_history(previous: list[dict[str, Any]] | None, current: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in [*(previous or []), *(current or [])]:
        if not isinstance(item, dict):
            continue
        if item.get("evidence_source") != "runtime" or item.get("verification_status") != "verified":
            continue
        environment = str(item.get("environment", ""))
        correlation_id = str(item.get("correlation_id", ""))
        merge_sha = str(item.get("merge_sha", ""))
        if environment not in VALID_ENVIRONMENTS or not correlation_id or not merge_sha:
            continue
        key = (environment, correlation_id, merge_sha)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    merged.sort(key=lambda item: str(item.get("timestamp", "")))
    return merged[-MAX_HISTORY:]


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", required=True, type=Path)
    parser.add_argument("--current", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = merge_history(_read(args.previous), _read(args.current))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
