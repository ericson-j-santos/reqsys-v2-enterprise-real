#!/usr/bin/env python3
import argparse
import json
from copy import deepcopy
from pathlib import Path

STABLE = "UX_DASHBOARD_CONTINUOUS_STABILITY_STABLE"
REVIEW = "UX_DASHBOARD_CONTINUOUS_STABILITY_REVIEW"


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _dump(path, payload):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build(history):
    samples = list(history.get("samples") or [])
    total = len(samples)
    ok_flags = [s.get("status") == "UX_DASHBOARD_CONTINUOUS_RELIABILITY_CARD_OK" for s in samples]
    success_count = sum(ok_flags)
    success_rate = round((success_count / total) * 100, 2) if total else 0.0

    stable_streak = 0
    for flag in reversed(ok_flags):
        if not flag:
            break
        stable_streak += 1

    recent = samples[-3:]
    recurring_drift = len(recent) >= 3 and sum(bool(s.get("drift_detected")) for s in recent) >= 2
    fingerprints = {s.get("fingerprint") for s in samples if s.get("fingerprint")}
    common_fingerprint = len(fingerprints) == 1 and total > 0
    score = max(0, min(100, round(success_rate - (25 if recurring_drift else 0), 2)))
    eligible = total >= 3 and success_rate == 100.0 and stable_streak >= 3 and common_fingerprint and not recurring_drift

    return {
        "status": STABLE if eligible else REVIEW,
        "sample_count": total,
        "success_rate": success_rate,
        "stable_streak": stable_streak,
        "confidence_score": score,
        "common_fingerprint": common_fingerprint,
        "recurring_drift": recurring_drift,
        "human_review_eligible": eligible,
        "guardrails": {
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
            "automatic_promotion": False,
            "deploy_changed": False,
            "readiness_changed": False,
            "production_ready_changed": False,
        },
    }


def consolidate(history, state, executive):
    indicator = build(history)
    state_out = deepcopy(state)
    executive_out = deepcopy(executive)
    state_out.setdefault("cards", {})["user_experience_dashboard_continuous_stability"] = indicator
    executive_out.setdefault("indicators", {})["user_experience_dashboard_continuous_stability"] = indicator
    return state_out, executive_out, indicator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--executive", required=True)
    parser.add_argument("--state-output", required=True)
    parser.add_argument("--executive-output", required=True)
    parser.add_argument("--indicator-output", required=True)
    args = parser.parse_args()
    state, executive, indicator = consolidate(_load(args.history), _load(args.state), _load(args.executive))
    _dump(args.state_output, state)
    _dump(args.executive_output, executive)
    _dump(args.indicator_output, indicator)


if __name__ == "__main__":
    main()
