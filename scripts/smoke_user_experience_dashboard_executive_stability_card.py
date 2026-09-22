#!/usr/bin/env python3
"""Valida sincronização do indicador entre Estado Único, Executive Brief e Ops Dashboard."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict

CARD_ID = "user-experience-dashboard-executive-stability"
FIELDS = (
    "status", "success_rate", "stable_sequence", "sample_count",
    "confidence_score", "common_fingerprint", "recurring_drift",
    "human_review_eligible", "mode", "production_blocker",
    "human_approval_required",
)


def canonical(value: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value.get(key) for key in FIELDS}


def fingerprint(value: Dict[str, Any]) -> str:
    payload = json.dumps(canonical(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evaluate(state: Dict[str, Any], brief: Dict[str, Any], dashboard: Dict[str, Any]) -> Dict[str, Any]:
    state_value = state.get("cards", {}).get("user_experience_dashboard_executive_stability", {})
    brief_value = brief.get("indicators", {}).get("user_experience_dashboard_executive_stability", {})
    matches = [item for item in dashboard.get("cards", []) if item.get("id") == CARD_ID]
    dashboard_value = matches[0] if len(matches) == 1 else {}
    values = [state_value, brief_value, dashboard_value]
    fps = [fingerprint(value) for value in values]
    guardrails_ok = all(
        value.get("mode") == "report-only"
        and value.get("production_blocker") is False
        and value.get("human_approval_required") is True
        for value in values
    )
    synchronized = len(set(fps)) == 1 and len(matches) == 1 and guardrails_ok
    return {
        "status": "UX_DASHBOARD_EXECUTIVE_STABILITY_CARD_OK" if synchronized else "UX_DASHBOARD_EXECUTIVE_STABILITY_CARD_REVIEW",
        "synchronized": synchronized,
        "duplicate_count": len(matches),
        "guardrails_ok": guardrails_ok,
        "fingerprints": {"state": fps[0], "brief": fps[1], "dashboard": fps[2]},
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
    load = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    report = evaluate(load(args.state), load(args.brief), load(args.dashboard))
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
