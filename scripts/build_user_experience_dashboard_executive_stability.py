#!/usr/bin/env python3
"""Consolida histórico do smoke de confiabilidade do Dashboard em modo report-only."""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

OK_STATUS = "UX_CONFIDENCE_DASHBOARD_RELIABILITY_CARD_OK"
STABLE_STATUS = "UX_DASHBOARD_EXECUTIVE_STABILITY_STABLE"
REVIEW_STATUS = "UX_DASHBOARD_EXECUTIVE_STABILITY_REVIEW"


def _load(path: str | None, default: Any) -> Any:
    if not path:
        return deepcopy(default)
    p = Path(path)
    if not p.exists():
        return deepcopy(default)
    return json.loads(p.read_text(encoding="utf-8"))


def _samples(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        raw = payload
    elif isinstance(payload, dict):
        raw = payload.get("samples", payload.get("history", []))
    else:
        raw = []
    return [item for item in raw if isinstance(item, dict)]


def build(history: Any, state: dict[str, Any], brief: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    samples = _samples(history)
    healthy = [s.get("status") == OK_STATUS and not bool(s.get("drift")) for s in samples]
    success_count = sum(healthy)
    success_rate = round((success_count / len(samples)) * 100, 2) if samples else 0.0

    stable_sequence = 0
    for item in reversed(healthy):
        if not item:
            break
        stable_sequence += 1

    recent = samples[-3:]
    recurring_drift = sum(bool(s.get("drift")) for s in recent) >= 2
    fingerprints = {str(s.get("fingerprint")) for s in samples if s.get("fingerprint")}
    common_fingerprint = next(iter(fingerprints)) if len(fingerprints) == 1 else None

    eligible = (
        len(samples) >= 3
        and success_rate == 100.0
        and stable_sequence >= 3
        and not recurring_drift
        and common_fingerprint is not None
    )
    status = STABLE_STATUS if eligible else REVIEW_STATUS
    score = max(0, min(100, round(success_rate - (20 if recurring_drift else 0))))

    indicator = {
        "status": status,
        "sample_count": len(samples),
        "success_count": success_count,
        "success_rate": success_rate,
        "stable_sequence": stable_sequence,
        "recurring_drift": recurring_drift,
        "common_fingerprint": common_fingerprint,
        "confidence_score": score,
        "human_review_eligible": eligible,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }

    out_state = deepcopy(state)
    out_state.setdefault("cards", {})["user_experience_dashboard_executive_stability"] = deepcopy(indicator)
    out_brief = deepcopy(brief)
    out_brief.setdefault("indicators", {})["user_experience_dashboard_executive_stability"] = deepcopy(indicator)
    return indicator, out_state, out_brief


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True)
    parser.add_argument("--state")
    parser.add_argument("--brief")
    parser.add_argument("--output", required=True)
    parser.add_argument("--state-output", required=True)
    parser.add_argument("--brief-output", required=True)
    args = parser.parse_args()

    indicator, state, brief = build(
        _load(args.history, []),
        _load(args.state, {}),
        _load(args.brief, {}),
    )
    Path(args.output).write_text(json.dumps(indicator, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    Path(args.state_output).write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    Path(args.brief_output).write_text(json.dumps(brief, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
