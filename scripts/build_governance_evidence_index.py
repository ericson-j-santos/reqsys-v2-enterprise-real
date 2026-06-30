#!/usr/bin/env python3
"""Build Governance Evidence Index JSON.

Gera um JSON estatico consumivel pelo dashboard operacional com as evidencias
centrais de governanca, workflows e artifacts esperados.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_OUTPUT = "docs/ops-dashboard/data/governance-evidence-index.json"
NEXT_INCREMENT_AFTER_DEEP_LINKS = "dashboard_trilha_d_history_card"


def workflow_runs_url(workflow_file: str) -> str:
    return f"https://github.com/{REPO}/actions/workflows/{workflow_file}"


def enrich_links(workflow_file: str, *, source: str | None = None) -> dict[str, str]:
    links = {
        "workflow": workflow_runs_url(workflow_file),
        "workflow_runs": workflow_runs_url(workflow_file),
        "latest_run": workflow_runs_url(workflow_file),
    }
    if source:
        links["source"] = source
    return links


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def evidence_items() -> list[dict[str, Any]]:
    return [
        {
            "id": "conflict_prediction",
            "title": "Conflict Prediction Gate",
            "workflow": "PR Conflict Guard",
            "script": "scripts/conflict_prediction_gate.py",
            "artifact": "conflict-prediction-gate-evidence",
            "json_path": "artifacts/conflict-prediction/conflict-prediction-gate.json",
            "status": "implemented",
            "dashboard_ready": True,
            "drilldown_fields": ["risk", "lane", "parallel_safe", "blocking_reasons", "signals"],
            "links": enrich_links(
                "pr-conflict-guard.yml",
                source=f"https://github.com/{REPO}/blob/main/scripts/conflict_prediction_gate.py",
            ),
        },
        {
            "id": "runtime_merge_queue",
            "title": "Runtime Merge Queue Gate",
            "workflow": "Governed Merge Queue",
            "script": "scripts/runtime_merge_queue_gate.py",
            "artifact": "governed-merge-queue-policy-evidence",
            "json_path": "artifacts/governed-merge-queue/runtime-merge-queue-gate.json",
            "status": "implemented",
            "dashboard_ready": True,
            "drilldown_fields": ["eligible", "state", "lane", "blocking_reasons", "evidence"],
            "links": enrich_links(
                "governed-merge-queue.yml",
                source=f"https://github.com/{REPO}/blob/main/scripts/runtime_merge_queue_gate.py",
            ),
        },
        {
            "id": "preview_environment",
            "title": "Preview Environment Contract",
            "workflow": "Preview Environment Contract",
            "script": None,
            "artifact": "preview-environment-evidence",
            "json_path": "artifacts/preview-environment/preview-environment-evidence.json",
            "status": "dry_run",
            "dashboard_ready": True,
            "drilldown_fields": ["mode", "pr", "environment", "url", "status", "checks", "correlation_id"],
            "links": enrich_links(
                "preview-environment-contract.yml",
                source=f"https://github.com/{REPO}/blob/main/.github/workflows/preview-environment-contract.yml",
            ),
        },
        {
            "id": "governed_pr_automation",
            "title": "Governed PR Automation",
            "workflow": "Governed PR Automation",
            "script": "scripts/governed_pr_increment_gate.py",
            "artifact": "governed-pr-increment-gate-evidence",
            "json_path": "artifacts/governed-pr-increment-gate/decision.json",
            "status": "implemented",
            "dashboard_ready": True,
            "drilldown_fields": ["allowed", "reason", "increment_type", "blockers", "recommended_actions"],
            "links": enrich_links(
                "governed-pr-automation.yml",
                source=f"https://github.com/{REPO}/blob/main/scripts/governed_pr_increment_gate.py",
            ),
        },
        {
            "id": "predictive_regression",
            "title": "Predictive Operational Regression Gate",
            "workflow": "Predictive Regression Guard",
            "script": "scripts/predict_operational_regression.py",
            "artifact": "predictive-regression-gate-evidence",
            "json_path": "artifacts/runtime-governance/predict-operational-regression-gate.json",
            "status": "dry_run",
            "dashboard_ready": True,
            "drilldown_fields": [
                "risk",
                "regression_predicted",
                "blocking_reasons",
                "signals",
                "dimension_risks",
                "recommendation",
            ],
            "links": enrich_links(
                "predictive-regression-guard.yml",
                source=f"https://github.com/{REPO}/blob/main/scripts/predict_operational_regression.py",
            ),
        },
        {
            "id": "pr_evidence_gate",
            "title": "PR Evidence Gate",
            "workflow": "PR Evidence Gate",
            "script": None,
            "artifact": "pr-evidence-gate",
            "json_path": "artifacts/pr-evidence-gate/pr-evidence-gate.json",
            "status": "implemented",
            "dashboard_ready": True,
            "drilldown_fields": ["pr", "head_sha", "checks", "evidence"],
            "links": enrich_links(
                "pr-evidence-gate.yml",
                source=f"https://github.com/{REPO}/blob/main/.github/workflows/pr-evidence-gate.yml",
            ),
        },
    ]


def build_payload() -> dict[str, Any]:
    items = evidence_items()
    implemented = sum(1 for item in items if item["status"] in {"implemented", "dry_run"})
    dashboard_ready = sum(1 for item in items if item["dashboard_ready"])
    score = round((implemented / len(items)) * 70 + (dashboard_ready / len(items)) * 30)

    return {
        "schema_version": "1.0.0",
        "repo": REPO,
        "generated_at": utc_now(),
        "overall_status": "green" if score >= 85 else "yellow",
        "governance_evidence_score": score,
        "summary": {
            "total_capabilities": len(items),
            "implemented_capabilities": implemented,
            "dashboard_ready_capabilities": dashboard_ready,
            "next_increment": NEXT_INCREMENT_AFTER_DEEP_LINKS,
        },
        "links": {
            "actions": f"https://github.com/{REPO}/actions",
            "pulls": f"https://github.com/{REPO}/pulls",
            "documentation": f"https://github.com/{REPO}/blob/main/docs/ops-dashboard/governance-evidence-index.md",
        },
        "evidence": items,
        "runtime_dashboard_contract": {
            "card_fields": ["title", "workflow", "status", "artifact", "dashboard_ready", "latest_run"],
            "drilldown_fields": ["links", "json_path", "drilldown_fields", "latest_run"],
            "refresh_strategy": "workflow_runs_deep_links_enabled",
        },
    }


def write_payload(output_path: str) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera governance-evidence-index.json para o dashboard operacional.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Imprime o payload gerado")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = write_payload(args.output)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"governance_evidence_score={payload['governance_evidence_score']} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
