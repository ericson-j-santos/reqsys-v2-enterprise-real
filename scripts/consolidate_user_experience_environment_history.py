#!/usr/bin/env python3
"""Consolida o histórico ambiental de UX no Estado Único e no Executive Brief."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CARD_KEY = "user_experience_environment_history"
REQUIRED_ENVIRONMENTS = {"DEV", "STG", "PROD"}


def build_card(history: dict[str, Any]) -> dict[str, Any]:
    environments = history.get("environments") or {}
    coverage = set(environments)
    pass_rates = {
        env: float((environments.get(env) or {}).get("pass_rate", 0))
        for env in sorted(REQUIRED_ENVIRONMENTS)
    }
    fingerprints = {
        (environments.get(env) or {}).get("fingerprint")
        for env in REQUIRED_ENVIRONMENTS
        if (environments.get(env) or {}).get("fingerprint")
    }
    complete = coverage == REQUIRED_ENVIRONMENTS
    pass_rate = min(pass_rates.values()) if pass_rates else 0.0
    no_drift = complete and len(fingerprints) == 1 and not bool(history.get("drift_detected", False))
    stable_sequence = int(history.get("stable_sequence", 1 if complete and pass_rate == 100 and no_drift else 0))
    eligible = complete and pass_rate == 100 and no_drift and stable_sequence >= 3
    return {
        "status": "eligible-for-human-review" if eligible else "collecting-evidence",
        "environment_coverage": sorted(coverage & REQUIRED_ENVIRONMENTS),
        "pass_rates": pass_rates,
        "minimum_pass_rate": pass_rate,
        "stable_sequence": stable_sequence,
        "common_fingerprint": next(iter(fingerprints)) if len(fingerprints) == 1 else None,
        "drift_detected": not no_drift,
        "eligible_for_human_review": eligible,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def consolidate(history: dict[str, Any], state: dict[str, Any], brief: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    card = build_card(history)
    state.setdefault("cards", {})[CARD_KEY] = card
    brief.setdefault("indicators", {})[CARD_KEY] = card
    return state, brief


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--brief", required=True)
    parser.add_argument("--state-output", required=True)
    parser.add_argument("--brief-output", required=True)
    args = parser.parse_args()

    history = json.loads(Path(args.history).read_text(encoding="utf-8"))
    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    brief = json.loads(Path(args.brief).read_text(encoding="utf-8"))
    state, brief = consolidate(history, state, brief)
    Path(args.state_output).write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    Path(args.brief_output).write_text(json.dumps(brief, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
