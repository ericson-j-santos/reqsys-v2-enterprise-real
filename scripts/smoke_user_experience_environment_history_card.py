#!/usr/bin/env python3
"""Smoke-check availability and synchronization of the UX environment-history card."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

CARD_ID = "user-experience-environment-history"
SOURCE_KEY = "user_experience_environment_history"
FIELDS = (
    "status",
    "environment_coverage",
    "pass_rate_by_environment",
    "minimum_pass_rate",
    "stable_sequence",
    "common_fingerprint",
    "drift_detected",
    "eligible_for_human_review",
    "mode",
    "production_blocker",
    "human_approval_required",
)


def canonical(value: dict[str, Any]) -> dict[str, Any]:
    return {field: value.get(field) for field in FIELDS}


def smoke(index: dict[str, Any], brief: dict[str, Any], dashboard: dict[str, Any]) -> dict[str, Any]:
    state = index.get("cards", {}).get(SOURCE_KEY) or {}
    executive = brief.get("indicators", {}).get(SOURCE_KEY) or {}
    cards = [card for card in dashboard.get("cards", []) if card.get("id") == CARD_ID]
    card = cards[0] if len(cards) == 1 else {}

    snapshots = {
        "state": canonical(state),
        "brief": canonical(executive),
        "dashboard": canonical(card),
    }
    serialized = [json.dumps(item, sort_keys=True, ensure_ascii=False) for item in snapshots.values()]
    synchronized = len(cards) == 1 and len(set(serialized)) == 1
    guardrails_ok = all(
        item.get("mode") == "report-only"
        and item.get("production_blocker") is False
        and item.get("human_approval_required") is True
        for item in snapshots.values()
    )
    digest = hashlib.sha256(serialized[0].encode("utf-8")).hexdigest() if synchronized else None
    return {
        "status": "UX_ENV_CARD_SYNC_OK" if synchronized and guardrails_ok else "UX_ENV_CARD_SYNC_REVIEW",
        "card_available": len(cards) == 1,
        "synchronized": synchronized,
        "guardrails_ok": guardrails_ok,
        "fingerprint": digest,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--brief", required=True)
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = smoke(
        json.loads(Path(args.index).read_text(encoding="utf-8")),
        json.loads(Path(args.brief).read_text(encoding="utf-8")),
        json.loads(Path(args.dashboard).read_text(encoding="utf-8")),
    )
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if result["status"] != "UX_ENV_CARD_SYNC_OK":
        raise SystemExit(result["status"])


if __name__ == "__main__":
    main()
