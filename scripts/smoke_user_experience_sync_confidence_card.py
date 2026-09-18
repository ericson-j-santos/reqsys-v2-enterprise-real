#!/usr/bin/env python3
"""Valida consistência do card de confiança UX entre Estado Único, Executive Brief e Dashboard."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

KEY = "user_experience_sync_confidence"
CARD_ID = "user-experience-sync-confidence"


def canonical(value: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "status", "confidence_level", "confidence_score", "sample_count",
        "sync_rate", "stable_sequence", "recurrent_drift",
        "human_review_eligible", "mode", "production_blocker",
        "human_approval_required",
    )
    return {field: value.get(field) for field in fields}


def validate(state: dict[str, Any], brief: dict[str, Any], dashboard: dict[str, Any]) -> dict[str, Any]:
    state_value = state.get("cards", {}).get(KEY, {})
    brief_value = brief.get("indicators", {}).get(KEY, {})
    matches = [card for card in dashboard.get("cards", []) if card.get("id") == CARD_ID]
    dashboard_value = matches[0] if len(matches) == 1 else {}

    payloads = [canonical(state_value), canonical(brief_value), canonical(dashboard_value)]
    fingerprints = [hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest() for item in payloads]
    guardrails_ok = all(
        item.get("mode") == "report-only"
        and item.get("production_blocker") is False
        and item.get("human_approval_required") is True
        for item in payloads
    )
    synchronized = len(matches) == 1 and len(set(fingerprints)) == 1 and guardrails_ok
    return {
        "status": "UX_SYNC_CONFIDENCE_CARD_OK" if synchronized else "UX_SYNC_CONFIDENCE_CARD_REVIEW",
        "synchronized": synchronized,
        "unique_card": len(matches) == 1,
        "guardrails_ok": guardrails_ok,
        "fingerprints": fingerprints,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--executive-brief", required=True)
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = validate(
        json.loads(Path(args.state).read_text(encoding="utf-8")),
        json.loads(Path(args.executive_brief).read_text(encoding="utf-8")),
        json.loads(Path(args.dashboard).read_text(encoding="utf-8")),
    )
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
