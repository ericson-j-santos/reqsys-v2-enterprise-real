#!/usr/bin/env python3
"""Build a report-only executive synchronization and stability index."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ENVIRONMENTS = ("DEV", "STG", "PROD")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _environment_metrics(history: dict[str, Any], environment: str) -> dict[str, Any]:
    source = history.get("environments", {}).get(environment, {})
    samples = list(source.get("samples", []))
    total = len(samples)
    passed = sum(1 for sample in samples if sample.get("passed") is True)
    synced = sum(1 for sample in samples if sample.get("synchronized") is True)
    stable_streak = 0
    for sample in reversed(samples):
        if sample.get("passed") is True and sample.get("synchronized") is True:
            stable_streak += 1
        else:
            break
    return {
        "samples": total,
        "pass_rate": round((passed / total) * 100, 2) if total else 0.0,
        "sync_rate": round((synced / total) * 100, 2) if total else 0.0,
        "stable_streak": stable_streak,
    }


def build_index(history: dict[str, Any]) -> dict[str, Any]:
    environments = {env: _environment_metrics(history, env) for env in ENVIRONMENTS}
    covered = [env for env, metrics in environments.items() if metrics["samples"] > 0]
    total_samples = sum(item["samples"] for item in environments.values())
    weighted_pass = (
        sum(item["pass_rate"] * item["samples"] for item in environments.values()) / total_samples
        if total_samples else 0.0
    )
    weighted_sync = (
        sum(item["sync_rate"] * item["samples"] for item in environments.values()) / total_samples
        if total_samples else 0.0
    )
    min_streak = min((item["stable_streak"] for item in environments.values()), default=0)
    score = round((weighted_pass * 0.45) + (weighted_sync * 0.45) + min(min_streak * 2, 100) * 0.10, 2)

    if len(covered) < 3:
        status = "insufficient-environment-coverage"
    elif weighted_pass < 95 or weighted_sync < 95:
        status = "attention"
    elif weighted_pass >= 99 and weighted_sync >= 99 and min_streak >= 20:
        status = "eligible-for-human-review"
    elif weighted_pass >= 98 and weighted_sync >= 98 and min_streak >= 10:
        status = "stable"
    else:
        status = "improving"

    return {
        "schema_version": "1.0",
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "status": status,
        "score": score,
        "coverage": {"covered": covered, "required": list(ENVIRONMENTS)},
        "total_samples": total_samples,
        "weighted_pass_rate": round(weighted_pass, 2),
        "weighted_sync_rate": round(weighted_sync, 2),
        "minimum_stable_streak": min_streak,
        "environments": environments,
        "eligible_for_human_review": status == "eligible-for-human-review",
    }


def enrich(runtime: dict[str, Any], brief: dict[str, Any], index: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime.setdefault("cards", {})["executive_sync_stability_index"] = index
    brief.setdefault("indicators", {})["executive_sync_stability_index"] = index
    return runtime, brief


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--brief", required=True, type=Path)
    args = parser.parse_args()

    index = build_index(_load(args.history))
    runtime, brief = enrich(_load(args.runtime), _load(args.brief), index)
    args.runtime.write_text(json.dumps(runtime, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.brief.write_text(json.dumps(brief, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(index, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
