#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path

CARD_ID = "user-experience-public-availability"
FIELDS = ("status", "coverage", "minimum_pass_rate", "sample_count", "stable_sequence", "common_fingerprint", "drift_detected", "degradation_detected", "human_review_eligible", "mode", "production_blocker", "human_approval_required")

def load(path): return json.loads(Path(path).read_text())
def canonical(value): return {k: value.get(k) for k in FIELDS}
def fingerprint(value): return hashlib.sha256(json.dumps(canonical(value), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True); ap.add_argument("--brief", required=True); ap.add_argument("--dashboard", required=True); ap.add_argument("--runtime", required=True); ap.add_argument("--output", required=True)
    a = ap.parse_args()
    state = load(a.state).get("cards", {}).get("user_experience_public_availability", {})
    brief = load(a.brief).get("indicators", {}).get("user_experience_public_availability", {})
    cards = [c for c in load(a.dashboard).get("cards", []) if c.get("id") == CARD_ID]
    runtime = load(a.runtime)
    dashboard = cards[0] if len(cards) == 1 else {}
    values = {"state": state, "brief": brief, "dashboard": dashboard, "runtime": runtime}
    fps = {k: fingerprint(v) for k, v in values.items()}
    guards = all(v.get("mode") == "report-only" and v.get("production_blocker") is False and v.get("human_approval_required") is True for v in values.values())
    synced = len(set(fps.values())) == 1 and len(cards) == 1 and guards
    result = {"status": "UX_PUBLIC_AVAILABILITY_SYNC_OK" if synced else "UX_PUBLIC_AVAILABILITY_SYNC_REVIEW", "synced": synced, "fingerprints": fps, "sources": list(values), "mode": "report-only", "production_blocker": False, "human_approval_required": True}
    Path(a.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(result["status"])

if __name__ == "__main__": main()
