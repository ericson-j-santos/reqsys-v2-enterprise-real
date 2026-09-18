#!/usr/bin/env python3
"""Propaga a tendência do smoke público do índice executivo ao Estado Único.

O enriquecimento é estritamente report-only: não altera readiness global,
production_ready, deploy ou qualquer decisão de promoção existente.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

ENVIRONMENTS = ("dev", "stg", "prod")
CARD_KEY = "executive_sync_stability_index_public_smoke_trend"


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Contrato JSON inválido em {path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _environment_summary(history: dict[str, Any], environment: str) -> dict[str, Any]:
    summary = history.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    samples = history.get("samples", [])
    if not isinstance(samples, list):
        samples = []
    scoped = [item for item in samples if isinstance(item, dict) and item.get("environment") == environment]
    latest = scoped[-1] if scoped else {}

    sample_count = _integer(summary.get("sample_count", len(scoped)), len(scoped))
    pass_rate = _number(summary.get("pass_rate", 0.0))
    stable_sequence = _integer(summary.get("stable_sequence", 0))
    latest_status = str(latest.get("status", "UNKNOWN"))
    latest_fingerprint = latest.get("fingerprint")
    eligible = (
        sample_count >= 3
        and pass_rate == 100.0
        and stable_sequence >= 3
        and latest_status == "PUBLIC_INDEX_SMOKE_OK"
    )

    return {
        "environment": environment,
        "sample_count": sample_count,
        "pass_rate_percent": round(pass_rate, 2),
        "stable_sequence": stable_sequence,
        "latest_status": latest_status,
        "latest_fingerprint": latest_fingerprint,
        "eligible_for_human_review": eligible,
        "production_blocker": False,
    }


def build_trend(histories: dict[str, dict[str, Any]]) -> dict[str, Any]:
    environments = {
        name: _environment_summary(histories.get(name, {}), name)
        for name in ENVIRONMENTS
    }
    covered = [name for name, item in environments.items() if item["sample_count"] > 0]
    missing = [name for name in ENVIRONMENTS if name not in covered]
    total_samples = sum(item["sample_count"] for item in environments.values())
    weighted_pass = (
        sum(item["pass_rate_percent"] * item["sample_count"] for item in environments.values())
        / total_samples
        if total_samples
        else 0.0
    )
    covered_items = [environments[name] for name in covered]
    minimum_pass = min((item["pass_rate_percent"] for item in covered_items), default=0.0)
    minimum_sequence = min((item["stable_sequence"] for item in covered_items), default=0)
    fingerprints = {
        item["latest_fingerprint"]
        for item in covered_items
        if item.get("latest_fingerprint")
    }
    synchronized = len(fingerprints) <= 1 and len(covered) == len(ENVIRONMENTS)
    coverage_complete = not missing
    eligible = coverage_complete and synchronized and all(
        item["eligible_for_human_review"] for item in environments.values()
    )

    if not coverage_complete:
        trend = "insufficient-environment-coverage"
    elif any(item["latest_status"] != "PUBLIC_INDEX_SMOKE_OK" for item in environments.values()):
        trend = "attention"
    elif not synchronized:
        trend = "drift-detected"
    elif eligible:
        trend = "eligible-for-human-review"
    elif minimum_pass >= 98.0 and minimum_sequence >= 2:
        trend = "stable"
    else:
        trend = "improving"

    return {
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
        "decision_scope": "human-review-only",
        "trend": trend,
        "coverage_complete": coverage_complete,
        "synchronized": synchronized,
        "covered_environments": covered,
        "missing_environments": missing,
        "environment_count": len(covered),
        "total_samples": total_samples,
        "weighted_pass_rate_percent": round(weighted_pass, 2),
        "minimum_pass_rate_percent": round(minimum_pass, 2),
        "minimum_stable_sequence": minimum_sequence,
        "eligible_for_human_review": eligible,
        "environments": environments,
    }


def enrich(
    runtime_index: dict[str, Any],
    executive_brief: dict[str, Any],
    histories: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = copy.deepcopy(runtime_index)
    brief = copy.deepcopy(executive_brief)
    trend = build_trend(histories)

    runtime.setdefault("cards", {})[CARD_KEY] = trend
    brief[CARD_KEY] = {
        "trend": trend["trend"],
        "coverage_complete": trend["coverage_complete"],
        "synchronized": trend["synchronized"],
        "total_samples": trend["total_samples"],
        "weighted_pass_rate_percent": trend["weighted_pass_rate_percent"],
        "minimum_stable_sequence": trend["minimum_stable_sequence"],
        "eligible_for_human_review": trend["eligible_for_human_review"],
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }
    return runtime, brief


def main() -> int:
    parser = argparse.ArgumentParser()
    for environment in ENVIRONMENTS:
        parser.add_argument(f"--{environment}-history", required=True, type=Path)
    parser.add_argument("--runtime-index", required=True, type=Path)
    parser.add_argument("--executive-brief", required=True, type=Path)
    parser.add_argument("--output-runtime-index", type=Path)
    parser.add_argument("--output-executive-brief", type=Path)
    args = parser.parse_args()

    histories = {
        name: _load(getattr(args, f"{name}_history"))
        for name in ENVIRONMENTS
    }
    runtime_path = args.output_runtime_index or args.runtime_index
    brief_path = args.output_executive_brief or args.executive_brief
    runtime, brief = enrich(
        _load(args.runtime_index),
        _load(args.executive_brief),
        histories,
    )
    _write(runtime_path, runtime)
    _write(brief_path, brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
