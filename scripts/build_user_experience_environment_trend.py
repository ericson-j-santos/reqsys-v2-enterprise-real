#!/usr/bin/env python3
"""Build an auditable UX environment trend from repeated dashboard smoke samples."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_ENVIRONMENTS = {"DEV", "STG", "PROD"}


def _fingerprint(sample: dict[str, Any]) -> str:
    canonical = {
        "environment_coverage": sorted(sample.get("environment_coverage") or []),
        "minimum_pass_rate": float(sample.get("minimum_pass_rate", 0)),
        "common_fingerprint": sample.get("common_fingerprint"),
        "drift_detected": bool(sample.get("drift_detected", True)),
        "sync_status": sample.get("sync_status"),
    }
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def build(samples: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = []
    for sample in samples:
        item = dict(sample)
        item["sample_fingerprint"] = _fingerprint(item)
        item["healthy"] = (
            set(item.get("environment_coverage") or []) == REQUIRED_ENVIRONMENTS
            and float(item.get("minimum_pass_rate", 0)) == 100
            and not bool(item.get("drift_detected", True))
            and bool(item.get("common_fingerprint"))
            and item.get("sync_status") == "UX_ENV_CARD_SYNC_OK"
        )
        normalized.append(item)

    total = len(normalized)
    healthy_count = sum(1 for item in normalized if item["healthy"])
    success_rate = round((healthy_count / total) * 100, 2) if total else 0
    stable_sequence = 0
    for item in reversed(normalized):
        if not item["healthy"]:
            break
        stable_sequence += 1

    recurring_drift = sum(1 for item in normalized[-5:] if item.get("drift_detected")) >= 2
    degradation = total >= 2 and normalized[-1].get("minimum_pass_rate", 0) < normalized[-2].get("minimum_pass_rate", 0)
    status = "UX_ENV_TREND_STABLE" if total >= 3 and success_rate == 100 and stable_sequence >= 3 else "UX_ENV_TREND_REVIEW"

    return {
        "status": status,
        "samples": normalized,
        "sample_count": total,
        "healthy_count": healthy_count,
        "success_rate": success_rate,
        "stable_sequence": stable_sequence,
        "recurring_drift": recurring_drift,
        "degradation_detected": degradation,
        "eligible_for_human_review": status == "UX_ENV_TREND_STABLE",
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.samples).read_text(encoding="utf-8"))
    samples = payload.get("samples", payload if isinstance(payload, list) else [])
    Path(args.output).write_text(json.dumps(build(samples), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
