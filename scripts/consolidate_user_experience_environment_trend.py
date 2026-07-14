#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

SOURCE_KEY = "user_experience_environment_trend"
CARD_ID = "user-experience-environment-trend"


def consolidate(trend: dict[str, Any]) -> dict[str, Any]:
    samples = int(trend.get("sample_count", 0))
    success_rate = float(trend.get("success_rate", 0))
    stable_sequence = int(trend.get("stable_sequence", 0))
    recurring_drift = bool(trend.get("recurring_drift", False))
    degradation = bool(trend.get("degradation_detected", False))
    status = trend.get("status", "UX_ENV_TREND_REVIEW")
    eligible = samples >= 3 and success_rate == 100 and stable_sequence >= 3 and not recurring_drift and not degradation and status == "UX_ENV_TREND_STABLE"
    return {
        "id": CARD_ID,
        "status": status,
        "sample_count": samples,
        "success_rate": success_rate,
        "stable_sequence": stable_sequence,
        "recurring_drift": recurring_drift,
        "degradation_detected": degradation,
        "fingerprints": trend.get("fingerprints", []),
        "eligible_for_human_review": eligible,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def enrich(state: dict[str, Any], brief: dict[str, Any], trend: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    card = consolidate(trend)
    state.setdefault("cards", {})[SOURCE_KEY] = card
    brief.setdefault("indicators", {})[SOURCE_KEY] = card
    return state, brief


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--trend", required=True); p.add_argument("--state", required=True); p.add_argument("--brief", required=True)
    p.add_argument("--state-output", required=True); p.add_argument("--brief-output", required=True)
    a = p.parse_args()
    trend = json.loads(Path(a.trend).read_text(encoding="utf-8"))
    state = json.loads(Path(a.state).read_text(encoding="utf-8")); brief = json.loads(Path(a.brief).read_text(encoding="utf-8"))
    state, brief = enrich(state, brief, trend)
    Path(a.state_output).write_text(json.dumps(state, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    Path(a.brief_output).write_text(json.dumps(brief, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")

if __name__ == "__main__": main()
