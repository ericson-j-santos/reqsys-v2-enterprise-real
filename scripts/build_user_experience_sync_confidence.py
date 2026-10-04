#!/usr/bin/env python3
"""Consolida tendência de sincronização das quatro fontes de UX.

Modo report-only: nunca promove ambientes nem altera readiness/production_ready.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

HEALTHY = "UX_PUBLIC_AVAILABILITY_SYNC_OK"


def _stable_streak(samples: list[dict[str, Any]]) -> int:
    streak = 0
    for sample in reversed(samples):
        if sample.get("status") == HEALTHY and not sample.get("drift_detected", False):
            streak += 1
        else:
            break
    return streak


def build(samples: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(samples)
    healthy = sum(
        1 for item in samples
        if item.get("status") == HEALTHY and not item.get("drift_detected", False)
    )
    sync_rate = round((healthy / total) * 100, 2) if total else 0.0
    stable_streak = _stable_streak(samples)
    recent = samples[-3:]
    recurring_drift = bool(recent) and sum(bool(x.get("drift_detected", False)) for x in recent) >= 2

    if total >= 3 and sync_rate == 100.0 and stable_streak >= 3 and not recurring_drift:
        confidence = "HIGH"
        score = 100
        status = "UX_SYNC_CONFIDENCE_STABLE"
        eligible = True
    elif total and sync_rate >= 80.0 and not recurring_drift:
        confidence = "MEDIUM"
        score = int(sync_rate)
        status = "UX_SYNC_CONFIDENCE_REVIEW"
        eligible = False
    else:
        confidence = "LOW"
        score = int(sync_rate)
        status = "UX_SYNC_CONFIDENCE_REVIEW"
        eligible = False

    indicator = {
        "status": status,
        "confidence_level": confidence,
        "confidence_score": score,
        "sample_count": total,
        "synchronized_samples": healthy,
        "sync_rate_percent": sync_rate,
        "stable_streak": stable_streak,
        "recurring_drift": recurring_drift,
        "human_review_eligible": eligible,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "automatic_promotion": False,
    }
    return indicator


def consolidate(payload: dict[str, Any]) -> dict[str, Any]:
    indicator = build(list(payload.get("samples", [])))
    state = dict(payload.get("state", {}))
    brief = dict(payload.get("executive_brief", {}))
    state.setdefault("cards", {})["user_experience_sync_confidence"] = indicator
    brief.setdefault("indicators", {})["user_experience_sync_confidence"] = indicator
    return {"indicator": indicator, "state": state, "executive_brief": brief}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = consolidate(source)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["indicator"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
