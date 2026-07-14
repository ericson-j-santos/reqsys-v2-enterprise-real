#!/usr/bin/env python3
"""Valida sincronização do indicador entre Estado Único, Executive Brief e Ops Dashboard."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict

CARD_ID = "user-experience-dashboard-continuous-reliability"
FIELDS = (
    "status", "success_rate", "stable_streak", "samples", "confidence_score",
    "common_fingerprint", "recurrent_drift", "human_review_eligible",
    "mode", "production_blocker", "human_approval_required",
)


def _canonical(value: Dict[str, Any] | None) -> Dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {field: source.get(field) for field in FIELDS}


def evaluate(state: Dict[str, Any], brief: Dict[str, Any], dashboard: Dict[str, Any]) -> Dict[str, Any]:
    state_value = state.get("cards", {}).get("user_experience_dashboard_continuous_reliability")
    brief_value = brief.get("indicators", {}).get("user_experience_dashboard_continuous_reliability")
    cards = [c for c in dashboard.get("cards", []) if isinstance(c, dict) and c.get("id") == CARD_ID]
    dashboard_value = cards[0] if len(cards) == 1 else None

    canonical = [_canonical(state_value), _canonical(brief_value), _canonical(dashboard_value)]
    synchronized = canonical[0] == canonical[1] == canonical[2]
    guardrails_ok = all(
        item.get("mode") == "report-only"
        and item.get("production_blocker") is False
        and item.get("human_approval_required") is True
        for item in canonical
    )
    payload = json.dumps(canonical[0], sort_keys=True, separators=(",", ":")).encode("utf-8")
    fingerprint = hashlib.sha256(payload).hexdigest()
    ok = synchronized and guardrails_ok and len(cards) == 1
    return {
        "classification": "UX_DASHBOARD_CONTINUOUS_RELIABILITY_CARD_OK" if ok else "UX_DASHBOARD_CONTINUOUS_RELIABILITY_CARD_REVIEW",
        "synchronized": synchronized,
        "guardrails_ok": guardrails_ok,
        "card_count": len(cards),
        "fingerprint": fingerprint,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--brief", required=True)
    parser.add_argument("--dashboard", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    result = evaluate(load(args.state), load(args.brief), load(args.dashboard))
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result["classification"].endswith("_REVIEW"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
