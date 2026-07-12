#!/usr/bin/env python3
"""Propaga a tendência do smoke público comparativo ao Estado Único e Executive Brief.

O enriquecimento é estritamente report-only: nunca altera readiness global,
production_ready ou qualquer decisão de promoção existente.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

ENVIRONMENTS = ("dev", "stg", "prod")
CARD_KEY = "executive_promotion_advisor_comparative_public_smoke_trend"


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
    env = history.get("environments", {}).get(environment, {})
    if not isinstance(env, dict):
        env = {}
    summary = env.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    entries = env.get("entries", [])
    if not isinstance(entries, list):
        entries = []

    latest = entries[-1] if entries and isinstance(entries[-1], dict) else {}
    sample_count = _integer(summary.get("sample_count", len(entries)), len(entries))
    pass_rate = _number(summary.get("pass_rate_percent", summary.get("success_rate_percent", 0.0)))
    visual_consistency = _number(
        summary.get("visual_consistency_percent", summary.get("consistency_percent", pass_rate))
    )
    stable_streak = _integer(summary.get("stable_streak", summary.get("success_streak", 0)))
    latest_status = str(summary.get("latest_status", latest.get("status", "UNKNOWN")))

    eligible = (
        sample_count >= 10
        and pass_rate >= 98.0
        and visual_consistency >= 98.0
        and stable_streak >= 5
        and latest_status not in {"PUBLIC_COMPARATIVE_SMOKE_REVIEW", "REVIEW", "FAILED"}
    )

    return {
        "environment": environment,
        "sample_count": sample_count,
        "pass_rate_percent": round(pass_rate, 2),
        "visual_consistency_percent": round(visual_consistency, 2),
        "stable_streak": stable_streak,
        "latest_status": latest_status,
        "eligible_for_human_review": eligible,
        "production_blocker": False,
    }


def build_trend(history: dict[str, Any]) -> dict[str, Any]:
    environments = {name: _environment_summary(history, name) for name in ENVIRONMENTS}
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
    minimum_consistency = min(
        (item["visual_consistency_percent"] for item in covered_items), default=0.0
    )
    minimum_streak = min((item["stable_streak"] for item in covered_items), default=0)
    coverage_complete = not missing
    eligible = coverage_complete and all(item["eligible_for_human_review"] for item in environments.values())

    if not coverage_complete or total_samples < 3:
        trend = "insufficient-environment-coverage"
    elif any(item["latest_status"] in {"PUBLIC_COMPARATIVE_SMOKE_REVIEW", "REVIEW", "FAILED"} for item in environments.values()):
        trend = "attention"
    elif minimum_pass < 95.0 or minimum_consistency < 95.0:
        trend = "attention"
    elif eligible:
        trend = "eligible-for-human-review"
    elif minimum_pass >= 98.0 and minimum_consistency >= 98.0 and minimum_streak >= 3:
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
        "covered_environments": covered,
        "missing_environments": missing,
        "environment_count": len(covered),
        "total_samples": total_samples,
        "weighted_pass_rate_percent": round(weighted_pass, 2),
        "minimum_pass_rate_percent": round(minimum_pass, 2),
        "minimum_visual_consistency_percent": round(minimum_consistency, 2),
        "minimum_stable_streak": minimum_streak,
        "eligible_for_human_review": eligible,
        "environments": environments,
    }


def enrich(runtime_index: dict[str, Any], executive_brief: dict[str, Any], history: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = copy.deepcopy(runtime_index)
    brief = copy.deepcopy(executive_brief)
    trend = build_trend(history)

    runtime.setdefault("cards", {})[CARD_KEY] = trend
    brief[CARD_KEY] = {
        "trend": trend["trend"],
        "coverage_complete": trend["coverage_complete"],
        "total_samples": trend["total_samples"],
        "weighted_pass_rate_percent": trend["weighted_pass_rate_percent"],
        "minimum_visual_consistency_percent": trend["minimum_visual_consistency_percent"],
        "minimum_stable_streak": trend["minimum_stable_streak"],
        "eligible_for_human_review": trend["eligible_for_human_review"],
        "mode": "report-only",
        "production_blocker": False,
        "human_approval_required": True,
    }
    return runtime, brief


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True, type=Path)
    parser.add_argument("--runtime-index", required=True, type=Path)
    parser.add_argument("--executive-brief", required=True, type=Path)
    parser.add_argument("--output-runtime-index", type=Path)
    parser.add_argument("--output-executive-brief", type=Path)
    args = parser.parse_args()

    runtime_path = args.output_runtime_index or args.runtime_index
    brief_path = args.output_executive_brief or args.executive_brief
    runtime, brief = enrich(_load(args.runtime_index), _load(args.executive_brief), _load(args.history))
    _write(runtime_path, runtime)
    _write(brief_path, brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
