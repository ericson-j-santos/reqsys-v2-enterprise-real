#!/usr/bin/env python3
"""Promove baselines de cobertura sem permitir regressão."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_REPORT = "artifacts/domain-coverage/report.json"
DEFAULT_POLICY = "config/domain-coverage-policy.json"
DEFAULT_HISTORY = "docs/ops-dashboard/data/domain-coverage-history.json"


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def promote(policy: dict[str, Any], report: dict[str, Any], *, measured_at: str, source_sha: str) -> tuple[dict[str, Any], dict[str, Any]]:
    current = {name: float(value) for name, value in (policy.get("baseline") or {}).items()}
    promoted = dict(current)
    changes: dict[str, dict[str, float | None]] = {}
    measured: dict[str, float] = {}

    for name, item in (report.get("domains") or {}).items():
        if not item.get("eligible_for_baseline", int(item.get("statements", 0)) > 0):
            continue
        value = round(float(item.get("coverage_percent", 0.0)), 2)
        measured[name] = value
        previous = current.get(name)
        if previous is None or value > previous:
            promoted[name] = value
            changes[name] = {"from": previous, "to": value}

    updated_policy = dict(policy)
    updated_policy["schema_version"] = "1.2.0"
    updated_policy["mode"] = "regression_blocking" if promoted else policy.get("mode", "record_then_regression")
    updated_policy["baseline"] = dict(sorted(promoted.items()))

    return updated_policy, {
        "measured_at": measured_at,
        "source_sha": source_sha,
        "status": "promoted" if changes else "unchanged",
        "measured": dict(sorted(measured.items())),
        "changes": changes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote domain coverage baseline")
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--history", default=DEFAULT_HISTORY)
    parser.add_argument("--source-sha", default="unknown")
    parser.add_argument("--measured-at", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args(argv)

    report = load_json(Path(args.report))
    if not report:
        raise SystemExit(f"coverage report not found or empty: {args.report}")
    policy_path = Path(args.policy)
    history_path = Path(args.history)
    policy = load_json(policy_path, {})
    history = load_json(history_path, {"schema_version": "1.0.0", "entries": []})
    updated_policy, entry = promote(policy, report, measured_at=args.measured_at, source_sha=args.source_sha)
    entries = list(history.get("entries") or [])
    if not entries or entries[-1] != entry:
        entries.append(entry)
    write_json(policy_path, updated_policy)
    write_json(history_path, {"schema_version": "1.0.0", "entries": entries[-100:]})
    print(json.dumps({"changed": updated_policy != policy, "entry": entry}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
