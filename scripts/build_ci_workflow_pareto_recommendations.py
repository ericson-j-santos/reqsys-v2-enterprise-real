#!/usr/bin/env python3
"""Gera recomendações Pareto para workflows de PR sem alterar execução.

Entrada: métricas produzidas por ``build_pr_workflow_run_metrics.py``.
Saída: ranking de workflows report-only por presença nos PRs e ganho potencial.

O script é offline, determinístico e report-only. Workflows protegidos nunca são
recomendados para filtro por path.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_METRICS = Path("docs/ops-dashboard/data/pr-workflow-run-metrics.json")
DEFAULT_POLICY = Path("config/ci-workflow-pareto-policy.json")
DEFAULT_OUTPUT = Path("docs/ops-dashboard/data/ci-workflow-pareto-recommendations.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_recommendations(metrics: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    prs = metrics.get("pull_requests") or []
    pr_count = len(prs)
    workflow_presence: Counter[str] = Counter()

    for pr in prs:
        if not isinstance(pr, dict):
            continue
        workflows = pr.get("workflows") or []
        workflow_presence.update(set(str(item) for item in workflows if item))

    protected = set(policy.get("protected_workflows") or [])
    report_only = set(policy.get("report_only_workflows") or [])
    minimum_sample = int(policy.get("minimum_pr_sample") or 3)
    minimum_presence = float(policy.get("minimum_presence_percent") or 50)
    minimum_saved = int(policy.get("minimum_potential_runs_saved") or 2)

    candidates: list[dict[str, Any]] = []
    protected_observed: list[dict[str, Any]] = []

    for workflow, count in workflow_presence.most_common():
        presence_percent = round((count / pr_count * 100), 2) if pr_count else 0
        item = {
            "workflow": workflow,
            "pr_presence_count": count,
            "pr_presence_percent": presence_percent,
        }

        if workflow in protected:
            protected_observed.append({**item, "decision": "PROTECTED_REQUIRED_GATE"})
            continue
        if workflow not in report_only:
            continue

        potential_runs_saved = max(0, count - 1)
        eligible = (
            pr_count >= minimum_sample
            and presence_percent >= minimum_presence
            and potential_runs_saved >= minimum_saved
        )
        candidates.append(
            {
                **item,
                "potential_runs_saved": potential_runs_saved,
                "decision": "RECOMMEND_PATH_REVIEW" if eligible else "KEEP_MEASURING",
                "reason": (
                    "volume_relevante_com_amostra_suficiente"
                    if eligible
                    else "amostra_ou_ganho_insuficiente"
                ),
                "automatic_change_allowed": False,
            }
        )

    candidates.sort(
        key=lambda item: (
            item["decision"] == "RECOMMEND_PATH_REVIEW",
            item["potential_runs_saved"],
            item["pr_presence_percent"],
        ),
        reverse=True,
    )
    recommended = [item for item in candidates if item["decision"] == "RECOMMEND_PATH_REVIEW"]

    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "mode": "report_only",
        "source_available": bool(metrics),
        "summary": {
            "pr_sample_count": pr_count,
            "observed_workflow_count": len(workflow_presence),
            "report_only_candidate_count": len(candidates),
            "recommended_path_review_count": len(recommended),
            "estimated_runs_saved_if_all_reviewed": sum(item["potential_runs_saved"] for item in recommended),
            "decision": "REVIEW_RECOMMENDED" if recommended else "KEEP_MEASURING",
        },
        "policy": {
            "minimum_pr_sample": minimum_sample,
            "minimum_presence_percent": minimum_presence,
            "minimum_potential_runs_saved": minimum_saved,
            "target_average_workflows_per_pr": policy.get("target_average_workflows_per_pr", 10),
            "automatic_filtering": False,
        },
        "recommendations": candidates,
        "protected_workflows_observed": protected_observed,
        "guardrails": [
            "required_gates_never_recommended_for_path_filtering",
            "recommendation_requires_measured_sample",
            "workflow_filter_change_requires_separate_pr",
            "rollback_required_for_each_future_filter_change",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera recomendações Pareto de workflows por PR")
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = build_recommendations(load_json(args.metrics), load_json(args.policy))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        summary = payload["summary"]
        print(
            f"decision={summary['decision']} "
            f"recommended={summary['recommended_path_review_count']} "
            f"output={args.output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
