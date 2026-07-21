#!/usr/bin/env python3
"""Constrói histórico persistente e alertas deduplicados do Flow Completion Monitor."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALERT_STATUSES = {"FAILED", "BLOCKED", "STALE"}


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def fingerprint(item: dict[str, Any]) -> str:
    next_expected = item.get("next_expected") or {}
    raw = "|".join(
        [
            str(item.get("execution_id") or ""),
            str(item.get("status") or ""),
            str(next_expected.get("environment") or ""),
            str(next_expected.get("stage") or ""),
            str(item.get("expected_commit_sha") or ""),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_state(report: dict[str, Any], previous: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    previous_fingerprints = set(previous.get("active_fingerprints") or [])
    active: list[dict[str, Any]] = []
    notifications: list[dict[str, Any]] = []

    for item in report.get("open_items") or []:
        if item.get("status") not in ALERT_STATUSES:
            continue
        current = dict(item)
        current["fingerprint"] = fingerprint(item)
        active.append(current)
        if current["fingerprint"] not in previous_fingerprints:
            notifications.append(current)

    history = list(previous.get("history") or [])
    history.append(
        {
            "observed_at": now.isoformat(),
            "summary": report.get("summary") or {},
            "active_alerts": len(active),
            "new_notifications": len(notifications),
        }
    )
    history = history[-168:]

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-flow-completion-alert-state",
        "generated_at": now.isoformat(),
        "active_fingerprints": sorted(item["fingerprint"] for item in active),
        "active_alerts": active,
        "new_notifications": notifications,
        "history": history,
        "automatic_remediation_allowed": False,
        "production_action_requires_human_approval": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--previous", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    state = build_state(load(args.report), load(args.previous))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"active": len(state["active_alerts"]), "new": len(state["new_notifications"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
