#!/usr/bin/env python3
"""Integra Workflow Efficiency ao Estado Único ReqSys e ao Runtime Executive Index.

Processador offline, idempotente e report-only. Consome apenas contratos JSON
estáticos e não realiza chamadas externas nem altera workflows.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_EFFICIENCY = Path("docs/ops-dashboard/data/ci-workflow-efficiency-dashboard.json")
DEFAULT_RUNTIME_INDEX = Path("docs/ops-dashboard/data/runtime-executive-index.json")
DEFAULT_STATE = Path("artifacts/main-operational-state-snapshot/main-operational-state-snapshot.json")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_card(efficiency: dict[str, Any]) -> dict[str, Any]:
    card = efficiency.get("executive_card") or {}
    summary = efficiency.get("summary") or {}
    top = efficiency.get("top_workflows") or []
    return {
        "available": bool(efficiency),
        "title": card.get("title", "Workflow Efficiency"),
        "status": card.get("status", "unknown"),
        "score_percent": float(card.get("score_percent") or 0),
        "trend_delta_points": float(card.get("trend_delta_points") or 0),
        "recommended_action": card.get("recommended_action", "KEEP_MEASURING"),
        "pr_sample_count": int(summary.get("pr_sample_count") or 0),
        "estimated_runs_saved": int(summary.get("estimated_runs_saved") or 0),
        "top_workflow": top[0].get("workflow") if top else None,
        "mode": efficiency.get("mode", "report_only"),
        "source_contract": "ci-workflow-efficiency-dashboard",
    }


def enrich_runtime_index(index: dict[str, Any], efficiency: dict[str, Any]) -> dict[str, Any]:
    payload = dict(index)
    cards = dict(payload.get("cards") or {})
    summary = dict(payload.get("summary") or {})
    links = dict(payload.get("links") or {})
    guardrails = list(payload.get("guardrails") or [])

    card = build_card(efficiency)
    cards["workflow_efficiency"] = card
    summary["workflow_efficiency_score"] = card["score_percent"]
    summary["workflow_efficiency_status"] = card["status"]
    links["workflow_efficiency"] = "data/ci-workflow-efficiency-dashboard.json"

    for guardrail in (
        "workflow_efficiency_is_report_only",
        "workflow_filters_require_separate_pr",
        "required_gates_never_optimized_automatically",
    ):
        if guardrail not in guardrails:
            guardrails.append(guardrail)

    payload["schema_version"] = "1.4.0"
    payload["cards"] = cards
    payload["summary"] = summary
    payload["links"] = links
    payload["guardrails"] = guardrails
    return payload


def enrich_state(state: dict[str, Any], efficiency: dict[str, Any]) -> dict[str, Any]:
    payload = dict(state)
    indicators = dict(payload.get("indicators") or {})
    card = build_card(efficiency)
    indicators["workflow_efficiency"] = card
    payload["indicators"] = indicators
    payload["workflow_efficiency_score"] = card["score_percent"]
    payload["workflow_efficiency_status"] = card["status"]
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Integra Workflow Efficiency ao Estado Único ReqSys")
    parser.add_argument("--efficiency", type=Path, default=DEFAULT_EFFICIENCY)
    parser.add_argument("--runtime-index", type=Path, default=DEFAULT_RUNTIME_INDEX)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()

    efficiency = load_json(args.efficiency)
    if not efficiency:
        raise SystemExit("workflow efficiency contract ausente")

    write_json(args.runtime_index, enrich_runtime_index(load_json(args.runtime_index), efficiency))
    if args.state.exists():
        write_json(args.state, enrich_state(load_json(args.state), efficiency))

    print(json.dumps({"status": "integrated", "score": build_card(efficiency)["score_percent"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
