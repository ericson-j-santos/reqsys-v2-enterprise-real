#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CARD_HOOK = "executive_sync_stability_index"
MAX_SAMPLES = 90


def _get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=20) as response:
        return response.read().decode("utf-8")


def _fingerprint(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def validate(base_url: str, environment: str) -> dict:
    html = _get(base_url.rstrip("/") + "/index.html")
    state = json.loads(_get(base_url.rstrip("/") + "/data/runtime-executive-index.json"))
    card = state.get("cards", {}).get(CARD_HOOK, {})
    checks = {
        "html_hook": CARD_HOOK in html,
        "card_present": bool(card),
        "report_only": card.get("mode") == "report-only",
        "non_blocking": card.get("production_blocker") is False,
        "human_approval": card.get("human_approval_required") is True,
    }
    passed = all(checks.values())
    return {
        "environment": environment,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "PUBLIC_INDEX_SMOKE_OK" if passed else "PUBLIC_INDEX_SMOKE_REVIEW",
        "passed": passed,
        "checks": checks,
        "fingerprint": _fingerprint(card) if card else None,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def append_history(history_path: Path, sample: dict) -> dict:
    history = {"samples": []}
    if history_path.exists():
        history = json.loads(history_path.read_text())
    samples = [s for s in history.get("samples", []) if s.get("environment") != sample["environment"] or s.get("fingerprint") != sample.get("fingerprint")]
    samples.append(sample)
    samples = samples[-MAX_SAMPLES:]
    environment_samples = [s for s in samples if s.get("environment") == sample["environment"]]
    stable_sequence = 0
    for item in reversed(environment_samples):
        if not item.get("passed"):
            break
        stable_sequence += 1
    pass_rate = round(100 * sum(1 for s in environment_samples if s.get("passed")) / max(1, len(environment_samples)), 2)
    result = {
        "samples": samples,
        "summary": {
            "environment": sample["environment"],
            "sample_count": len(environment_samples),
            "pass_rate": pass_rate,
            "stable_sequence": stable_sequence,
            "eligible_for_human_review": len(environment_samples) >= 3 and pass_rate == 100 and stable_sequence >= 3,
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
        },
    }
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--environment", choices=["dev", "stg", "prod"], required=True)
    parser.add_argument("--history", default="artifacts/executive-sync-stability-index-public-history.json")
    parser.add_argument("--output", default="artifacts/executive-sync-stability-index-public-smoke.json")
    args = parser.parse_args()
    sample = validate(args.base_url, args.environment)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(sample, indent=2, ensure_ascii=False) + "\n")
    append_history(Path(args.history), sample)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
