#!/usr/bin/env python3
"""Valida sincronização do indicador UX entre Estado Único, Executive Brief e Dashboard."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

CARD_ID = "user-experience-evidence"
STATE_KEY = "user_experience_evidence"


def _canonical(value: dict[str, Any]) -> str:
    payload = {
        "score": int(value.get("score", value.get("value", 0)) or 0),
        "status": value.get("status"),
        "evidenced": bool(value.get("evidenced", False)),
        "consolidated": bool(value.get("consolidated", False)),
        "mode": value.get("mode"),
        "production_blocker": value.get("production_blocker"),
        "human_approval_required": value.get("human_approval_required"),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_sync(state: dict[str, Any], brief: dict[str, Any], dashboard: dict[str, Any]) -> dict[str, Any]:
    state_value = state.get("cards", {}).get(STATE_KEY, {})
    brief_value = brief.get("indicators", {}).get(STATE_KEY, {})
    cards = [card for card in dashboard.get("cards", []) if card.get("id") == CARD_ID]
    errors: list[str] = []
    if len(cards) != 1:
        errors.append(f"expected exactly one {CARD_ID} card, found {len(cards)}")
        dashboard_value: dict[str, Any] = {}
    else:
        dashboard_value = cards[0]

    values = [state_value, brief_value, dashboard_value]
    for name, value in zip(("state", "brief", "dashboard"), values):
        if value.get("mode") != "report-only":
            errors.append(f"{name}: mode must be report-only")
        if value.get("production_blocker") is not False:
            errors.append(f"{name}: production_blocker must be false")
        if value.get("human_approval_required") is not True:
            errors.append(f"{name}: human approval must remain required")
        if bool(value.get("evidenced")) and int(value.get("score", value.get("value", 0)) or 0) != 92:
            errors.append(f"{name}: evidenced UX score must be 92")

    fingerprints = [_canonical(value) for value in values]
    synchronized = len(set(fingerprints)) == 1 and not errors
    digest = hashlib.sha256(fingerprints[0].encode("utf-8")).hexdigest() if synchronized else None
    return {
        "status": "PUBLIC_UX_SYNC_OK" if synchronized else "PUBLIC_UX_SYNC_REVIEW",
        "synchronized": synchronized,
        "fingerprint": digest,
        "errors": errors,
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
    result = validate_sync(load(args.state), load(args.brief), load(args.dashboard))
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not result["synchronized"]:
        raise SystemExit("\n".join(result["errors"]) or "public UX state is not synchronized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
