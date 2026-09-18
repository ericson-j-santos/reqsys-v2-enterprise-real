#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

SCHEMA_VERSION = "1.0.0"
MINIMUM_SAMPLES = 3
MINIMUM_CONSECUTIVE_QUALIFIED = 2


def _qualified(sample: dict[str, Any]) -> bool:
    return (
        sample.get("ux_100_ready") is True
        and float(sample.get("recovery_rate", 0)) >= 60
        and float(sample.get("average_recovery_seconds", 10**9)) <= 30
    )


def evaluate(history: list[dict[str, Any]] | None) -> dict[str, Any]:
    samples = [item for item in (history or []) if isinstance(item, dict)]
    qualified = [_qualified(sample) for sample in samples]
    consecutive = 0
    for value in reversed(qualified):
        if not value:
            break
        consecutive += 1

    rates = [float(item.get("recovery_rate", 0)) for item in samples]
    averages = [float(item.get("average_recovery_seconds", 0)) for item in samples]
    minimum_samples_met = len(samples) >= MINIMUM_SAMPLES
    stability_met = consecutive >= MINIMUM_CONSECUTIVE_QUALIFIED
    standard_gold_ready = minimum_samples_met and stability_met

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "UX_STANDARD_GOLD_EVIDENCE_READY" if standard_gold_ready else "UX_STABILITY_EVIDENCE_PENDING",
        "standard_gold_ready": standard_gold_ready,
        "sample_count": len(samples),
        "qualified_sample_count": sum(qualified),
        "consecutive_qualified_samples": consecutive,
        "recovery_rate_average": round(mean(rates), 1) if rates else 0.0,
        "recovery_seconds_average": round(mean(averages), 1) if averages else 0.0,
        "criteria": {
            "minimum_samples": MINIMUM_SAMPLES,
            "minimum_samples_met": minimum_samples_met,
            "minimum_consecutive_qualified": MINIMUM_CONSECUTIVE_QUALIFIED,
            "stability_met": stability_met,
        },
        "mode": "advisory",
        "production_blocker": False,
        "human_approval_required": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    history = json.loads(args.history.read_text(encoding="utf-8"))
    if not isinstance(history, list):
        raise ValueError("history deve ser uma lista JSON")

    report = evaluate(history)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
