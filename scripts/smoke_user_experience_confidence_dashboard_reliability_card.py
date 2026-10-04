#!/usr/bin/env python3
"""Valida sincronização do indicador de confiabilidade entre as três fontes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

CARD_ID = "user-experience-confidence-dashboard-reliability"
FIELDS = (
    "status",
    "availability_rate",
    "stable_sequence",
    "sample_count",
    "confidence_score",
    "common_fingerprint",
    "recurring_drift",
    "human_review_eligible",
    "mode",
    "production_blocker",
    "human_approval_required",
)


def canonical(value: dict[str, Any]) -> dict[str, Any]:
    return {field: value.get(field) for field in FIELDS}


def fingerprint(value: dict[str, Any]) -> str:
    raw = json.dumps(canonical(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def evaluate(state: dict[str, Any], brief: dict[str, Any], dashboard: dict[str, Any]) -> dict[str, Any]:
    state_value = state.get("cards", {}).get("user_experience_sync_confidence_availability", {})
    brief_value = brief.get("indicators", {}).get("user_experience_sync_confidence_availability", {})
    matches = [card for card in dashboard.get("cards", []) if card.get("id") == CARD_ID]
    dashboard_value = matches[0] if len(matches) == 1 else {}
    values = [state_value, brief_value, dashboard_value]
    fingerprints = [fingerprint(item) for item in values]
    guardrails_ok = all(
        item.get("mode") == "report-only"
        and item.get("production_blocker") is False
        and item.get("human_approval_required") is True
        for item in values
    )
    synchronized = len(matches) == 1 and len(set(fingerprints)) == 1 and guardrails_ok
    return {
        "status": "UX_CONFIDENCE_DASHBOARD_RELIABILITY_CARD_OK" if synchronized else "UX_CONFIDENCE_DASHBOARD_RELIABILITY_CARD_REVIEW",
        "synchronized": synchronized,
        "duplicate_count": len(matches),
        "guardrails_ok": guardrails_ok,
        "fingerprints": {
            "state": fingerprints[0],
            "executive_brief": fingerprints[1],
            "dashboard": fingerprints[2],
        },
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--brief", required=True)
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    result = evaluate(load(args.state), load(args.brief), load(args.dashboard))
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if result["synchronized"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
