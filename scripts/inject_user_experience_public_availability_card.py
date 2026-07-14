#!/usr/bin/env python3
import argparse, json
from pathlib import Path

CARD_ID = "user-experience-public-availability"

def load(path):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}

def build(state):
    src = state.get("cards", {}).get("user_experience_public_availability", {})
    return {
        "id": CARD_ID,
        "title": "UX Public Availability",
        "status": src.get("status", "PUBLIC_AVAILABILITY_REVIEW"),
        "coverage": src.get("coverage", []),
        "minimum_pass_rate": src.get("minimum_pass_rate", 0),
        "sample_count": src.get("sample_count", 0),
        "stable_sequence": src.get("stable_sequence", 0),
        "common_fingerprint": src.get("common_fingerprint"),
        "drift_detected": bool(src.get("drift_detected", True)),
        "degradation_detected": bool(src.get("degradation_detected", True)),
        "human_review_eligible": bool(src.get("human_review_eligible", False)),
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--dashboard", required=True)
    args = ap.parse_args()
    state, dashboard = load(args.state), load(args.dashboard)
    cards = [c for c in dashboard.get("cards", []) if c.get("id") != CARD_ID]
    cards.append(build(state))
    dashboard["cards"] = cards
    Path(args.dashboard).write_text(json.dumps(dashboard, indent=2, sort_keys=True) + "\n")

if __name__ == "__main__":
    main()
