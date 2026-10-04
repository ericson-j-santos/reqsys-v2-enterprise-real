#!/usr/bin/env python3
"""Propaga o histórico da homologação aos contratos executivos em report-only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def summarize(history: dict[str, Any]) -> dict[str, Any]:
    summary = history.get("summary") or {}
    return {
        "available": bool(history),
        "mode": "report-only",
        "sample_count": int(summary.get("sample_count") or 0),
        "pass_rate_percent": float(summary.get("pass_rate_percent") or 0),
        "stable_streak": int(summary.get("stable_streak") or 0),
        "trend": summary.get("trend") or "stable",
        "trend_delta_points": float(summary.get("trend_delta_points") or 0),
        "eligible_for_blocking_review": bool(summary.get("eligible_for_blocking_review")),
        "production_blocker": False,
        "policy": {
            "minimum_samples": 30,
            "minimum_pass_rate_percent": 98.0,
            "minimum_stable_streak": 20,
        },
    }


def enrich_runtime(index: dict[str, Any], trend: dict[str, Any]) -> dict[str, Any]:
    payload = dict(index)
    cards = dict(payload.get("cards") or {})
    links = dict(payload.get("links") or {})
    summary = dict(payload.get("summary") or {})
    cards["workflow_efficiency_homologation_trend"] = trend
    links["workflow_efficiency_homologation_history"] = "artifacts/workflow-efficiency-homologation-history/history.json"
    summary["workflow_efficiency_blocking_review_eligible"] = trend["eligible_for_blocking_review"]
    payload["cards"] = cards
    payload["links"] = links
    payload["summary"] = summary
    payload["schema_version"] = "1.4.0"
    return payload


def enrich_brief(brief: dict[str, Any], trend: dict[str, Any]) -> dict[str, Any]:
    payload = dict(brief)
    indicators = dict(payload.get("indicadores") or {})
    evidences = dict(payload.get("evidencias") or {})
    indicators["workflow_efficiency_homologation_sample_count"] = trend["sample_count"]
    indicators["workflow_efficiency_homologation_pass_rate_percent"] = trend["pass_rate_percent"]
    indicators["workflow_efficiency_homologation_stable_streak"] = trend["stable_streak"]
    indicators["workflow_efficiency_blocking_review_eligible"] = trend["eligible_for_blocking_review"]
    evidences["workflow_efficiency_homologation_trend"] = trend
    payload["indicadores"] = indicators
    payload["evidencias"] = evidences
    return payload


def enrich_readiness(gate: dict[str, Any], trend: dict[str, Any]) -> dict[str, Any]:
    payload = dict(gate)
    domains = dict(payload.get("domains") or {})
    domains["workflow_efficiency_homologation_trend"] = {
        "id": "workflow_efficiency_homologation_trend",
        "label": "Tendência de homologação Workflow Efficiency",
        "state": "green" if trend["eligible_for_blocking_review"] else "yellow",
        "score": 100 if trend["eligible_for_blocking_review"] else 70,
        "available": trend["available"],
        "detail": (
            f"samples={trend['sample_count']}; pass_rate={trend['pass_rate_percent']}%; "
            f"stable_streak={trend['stable_streak']}; trend={trend['trend']}; report_only=true"
        ),
        "production_blocker": False,
        "report_only": True,
    }
    payload["domains"] = domains
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Propaga tendência da homologação Workflow Efficiency")
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--runtime-index", type=Path, required=True)
    parser.add_argument("--executive-brief", type=Path, required=True)
    parser.add_argument("--executive-readiness", type=Path, required=True)
    args = parser.parse_args()

    history = load_json(args.history)
    if not history:
        raise SystemExit("histórico ausente ou inválido")
    trend = summarize(history)
    write_json(args.runtime_index, enrich_runtime(load_json(args.runtime_index), trend))
    write_json(args.executive_brief, enrich_brief(load_json(args.executive_brief), trend))
    write_json(args.executive_readiness, enrich_readiness(load_json(args.executive_readiness), trend))
    print(json.dumps({"status": "enriched", **trend}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
