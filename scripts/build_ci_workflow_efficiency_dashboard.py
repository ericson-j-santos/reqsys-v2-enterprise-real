#!/usr/bin/env python3
"""Gera dashboard executivo de eficiência de workflows a partir do Pareto.

O builder é offline, determinístico e report-only. Ele não altera workflows,
branch protection, merge queue ou gates obrigatórios.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_INPUT = Path("docs/ops-dashboard/data/ci-workflow-pareto-recommendations.json")
DEFAULT_OUTPUT = Path("docs/ops-dashboard/data/ci-workflow-efficiency-dashboard.json")
DEFAULT_HISTORY = Path("docs/ops-dashboard/data/history/ci-workflow-efficiency-history.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def calculate_efficiency_score(recommendations: list[dict[str, Any]]) -> float:
    total_observed = sum(int(item.get("pr_presence_count") or 0) for item in recommendations)
    total_savable = sum(int(item.get("potential_runs_saved") or 0) for item in recommendations)
    if total_observed <= 0:
        return 100.0
    necessary = max(0, total_observed - total_savable)
    return round((necessary / total_observed) * 100, 2)


def build_dashboard(source: dict[str, Any], previous_history: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    recommendations = [item for item in source.get("recommendations", []) if isinstance(item, dict)]
    recommendations.sort(
        key=lambda item: (
            int(item.get("potential_runs_saved") or 0),
            float(item.get("pr_presence_percent") or 0),
        ),
        reverse=True,
    )

    score = calculate_efficiency_score(recommendations)
    previous_entries = list((previous_history or {}).get("entries") or [])
    previous_score = float(previous_entries[-1].get("workflow_efficiency_score") or score) if previous_entries else score
    trend_delta = round(score - previous_score, 2)

    top_workflows = []
    for index, item in enumerate(recommendations[:10], start=1):
        observed = int(item.get("pr_presence_count") or 0)
        savable = int(item.get("potential_runs_saved") or 0)
        savings_percent = round((savable / observed) * 100, 2) if observed else 0
        top_workflows.append(
            {
                "rank": index,
                "workflow": item.get("workflow", "unknown"),
                "pr_presence_count": observed,
                "pr_presence_percent": float(item.get("pr_presence_percent") or 0),
                "potential_runs_saved": savable,
                "potential_savings_percent": savings_percent,
                "decision": item.get("decision", "KEEP_MEASURING"),
                "priority": "high" if index <= 3 and savable > 0 else "medium" if savable > 0 else "low",
            }
        )

    now = utc_now()
    summary = source.get("summary") or {}
    dashboard = {
        "schema_version": "1.0.0",
        "generated_at": now,
        "mode": "report_only",
        "source_available": bool(source),
        "executive_card": {
            "title": "Workflow Efficiency",
            "score_percent": score,
            "trend_delta_points": trend_delta,
            "status": "green" if score >= 85 else "yellow" if score >= 70 else "red",
            "recommended_action": "REVIEW_TOP_WORKFLOW" if top_workflows and top_workflows[0]["potential_runs_saved"] > 0 else "KEEP_MEASURING",
        },
        "summary": {
            "pr_sample_count": int(summary.get("pr_sample_count") or 0),
            "observed_workflow_count": int(summary.get("observed_workflow_count") or 0),
            "recommended_path_review_count": int(summary.get("recommended_path_review_count") or 0),
            "estimated_runs_saved": sum(item["potential_runs_saved"] for item in top_workflows),
            "workflow_efficiency_score": score,
        },
        "top_workflows": top_workflows,
        "guardrails": [
            "report_only",
            "no_automatic_workflow_change",
            "required_gates_protected",
            "separate_pr_required_for_path_filter",
            "before_after_evidence_required",
        ],
    }

    history_entry = {
        "generated_at": now,
        "workflow_efficiency_score": score,
        "trend_delta_points": trend_delta,
        "pr_sample_count": dashboard["summary"]["pr_sample_count"],
        "estimated_runs_saved": dashboard["summary"]["estimated_runs_saved"],
        "top_workflow": top_workflows[0]["workflow"] if top_workflows else None,
    }
    entries = (previous_entries + [history_entry])[-30:]
    history = {"schema_version": "1.0.0", "entries": entries}
    return dashboard, history


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera dashboard de eficiência de workflows")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    dashboard, history = build_dashboard(load_json(args.input), load_json(args.history))
    write_json(args.output, dashboard)
    write_json(args.history, history)

    if args.json:
        print(json.dumps(dashboard, indent=2, ensure_ascii=False))
    else:
        card = dashboard["executive_card"]
        print(f"status={card['status']} score={card['score_percent']} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
