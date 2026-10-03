#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CARD_KEY = "executive_sync_stability_index_public_smoke_trend"
MAX_SAMPLES = 90


def _get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=20) as response:
        return response.read().decode("utf-8")


def _canonical(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "trend",
        "coverage_complete",
        "synchronized",
        "total_samples",
        "weighted_pass_rate_percent",
        "minimum_stable_sequence",
        "eligible_for_human_review",
        "mode",
        "production_blocker",
        "human_approval_required",
    )
    return {key: payload.get(key) for key in keys}


def _fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(_canonical(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate(base_url: str, environment: str) -> dict[str, Any]:
    root = base_url.rstrip("/")
    html = _get(root + "/index.html")
    runtime = json.loads(_get(root + "/data/runtime-executive-index.json"))
    brief = json.loads(_get(root + "/data/executive-brief.json"))
    runtime_card = runtime.get("cards", {}).get(CARD_KEY, {})
    brief_card = brief.get(CARD_KEY, {})

    runtime_fp = _fingerprint(runtime_card) if runtime_card else None
    brief_fp = _fingerprint(brief_card) if brief_card else None
    checks = {
        "html_hook": CARD_KEY in html,
        "runtime_card_present": bool(runtime_card),
        "brief_card_present": bool(brief_card),
        "report_only": runtime_card.get("mode") == "report-only" and brief_card.get("mode") == "report-only",
        "non_blocking": runtime_card.get("production_blocker") is False and brief_card.get("production_blocker") is False,
        "human_approval": runtime_card.get("human_approval_required") is True and brief_card.get("human_approval_required") is True,
        "runtime_brief_sync": bool(runtime_fp and brief_fp and runtime_fp == brief_fp),
    }
    passed = all(checks.values())
    return {
        "environment": environment,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "PUBLIC_TREND_SYNC_OK" if passed else "PUBLIC_TREND_SYNC_REVIEW",
        "passed": passed,
        "checks": checks,
        "fingerprint": runtime_fp,
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def append_history(path: Path, sample: dict[str, Any]) -> dict[str, Any]:
    history: dict[str, Any] = {"samples": []}
    if path.exists():
        history = json.loads(path.read_text(encoding="utf-8"))
    samples = history.get("samples", [])
    if not isinstance(samples, list):
        samples = []
    identity = (sample.get("environment"), sample.get("fingerprint"), sample.get("status"))
    samples = [
        item for item in samples
        if (item.get("environment"), item.get("fingerprint"), item.get("status")) != identity
    ]
    samples.append(sample)
    samples = samples[-MAX_SAMPLES:]
    scoped = [item for item in samples if item.get("environment") == sample.get("environment")]
    stable_sequence = 0
    for item in reversed(scoped):
        if not item.get("passed"):
            break
        stable_sequence += 1
    pass_rate = round(100 * sum(1 for item in scoped if item.get("passed")) / max(1, len(scoped)), 2)
    result = {
        "samples": samples,
        "summary": {
            "environment": sample.get("environment"),
            "sample_count": len(scoped),
            "pass_rate": pass_rate,
            "stable_sequence": stable_sequence,
            "eligible_for_human_review": len(scoped) >= 3 and pass_rate == 100 and stable_sequence >= 3,
            "mode": "report-only",
            "production_blocker": False,
            "human_approval_required": True,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--environment", choices=["dev", "stg", "prod"], required=True)
    parser.add_argument("--history", default="artifacts/executive-sync-stability-index-public-smoke-trend-sync-history.json")
    parser.add_argument("--output", default="artifacts/executive-sync-stability-index-public-smoke-trend-sync.json")
    args = parser.parse_args()
    sample = validate(args.base_url, args.environment)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(sample, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    append_history(Path(args.history), sample)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
