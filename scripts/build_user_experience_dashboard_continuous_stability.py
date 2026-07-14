#!/usr/bin/env python3
"""Consolida o histórico do smoke do card de confiabilidade contínua do Dashboard UX."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

OK = "UX_DASHBOARD_CONTINUOUS_RELIABILITY_CARD_OK"
STABLE = "UX_DASHBOARD_CONTINUOUS_STABILITY_STABLE"
REVIEW = "UX_DASHBOARD_CONTINUOUS_STABILITY_REVIEW"
KEY = "user_experience_dashboard_continuous_stability"


def _samples(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        raw = payload
    elif isinstance(payload, dict):
        raw = payload.get("samples", payload.get("history", []))
    else:
        raw = []
    return [item for item in raw if isinstance(item, dict)]


def build(history: Any) -> dict[str, Any]:
    samples = _samples(history)
    healthy = [
        item.get("classification") == OK
        and item.get("synchronized") is True
        and item.get("guardrails_ok") is True
        and int(item.get("card_count", 0)) == 1
        for item in samples
    ]
    total = len(samples)
    success_count = sum(healthy)
    success_rate = round(success_count / total * 100.0, 2) if total else 0.0

    stable_sequence = 0
    for item in reversed(healthy):
        if not item:
            break
        stable_sequence += 1

    recent = samples[-3:]
    recurring_drift = len(recent) == 3 and sum(not ok for ok in healthy[-3:]) >= 2
    fingerprints = {
        str(item.get("fingerprint"))
        for item, ok in zip(samples, healthy)
        if ok and item.get("fingerprint")
    }
    common_fingerprint = next(iter(fingerprints)) if len(fingerprints) == 1 else None
    eligible = (
        total >= 3
        and success_rate == 100.0
        and stable_sequence >= 3
        and common_fingerprint is not None
        and not recurring_drift
    )
    confidence_score = max(0, min(100, round(success_rate - (25 if recurring_drift else 0))))

    return {
        "status": STABLE if eligible else REVIEW,
        "sample_count": total,
        "success_count": success_count,
        "success_rate": success_rate,
        "stable_sequence": stable_sequence,
        "confidence_score": confidence_score,
        "common_fingerprint": common_fingerprint,
        "recurring_drift": recurring_drift,
        "human_review_eligible": eligible,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def consolidate(history: Any, state: dict[str, Any], brief: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    indicator = build(history)
    state_out = copy.deepcopy(state)
    brief_out = copy.deepcopy(brief)
    state_out.setdefault("cards", {})[KEY] = copy.deepcopy(indicator)
    brief_out.setdefault("indicators", {})[KEY] = copy.deepcopy(indicator)
    return indicator, state_out, brief_out


def _load(path: Path, default: Any) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--brief", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--state-output", required=True, type=Path)
    parser.add_argument("--brief-output", required=True, type=Path)
    args = parser.parse_args()

    indicator, state, brief = consolidate(
        _load(args.history, {"samples": []}),
        _load(args.state, {}),
        _load(args.brief, {}),
    )
    _write(args.output, indicator)
    _write(args.state_output, state)
    _write(args.brief_output, brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
