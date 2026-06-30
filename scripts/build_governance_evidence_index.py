#!/usr/bin/env python3
"""Build Governance Evidence Index JSON.

Gera um JSON estatico consumivel pelo dashboard operacional com as evidencias
centrais de governanca, workflows e artifacts esperados.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.build_trilha_d_history import coverage_targeted_surface_ready

REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_OUTPUT = "docs/ops-dashboard/data/governance-evidence-index.json"
DEFAULT_TRILHA_D_HISTORY = "docs/ops-dashboard/data/trilha-d-history.json"
NEXT_INCREMENT_AFTER_DEEP_LINKS = "dashboard_trilha_d_history_card"
NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD = "artifact_ingestion_refresh"
NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION = "continuous_trilha_d_monitoring"
NEXT_INCREMENT_AFTER_CONTINUOUS_MONITORING = "coverage_targeted_tests"
NEXT_INCREMENT_AFTER_COVERAGE_TARGETED = "link_governance_cards_to_latest_workflow_runs"

WORKFLOW_FILE_BY_EVIDENCE_ID: dict[str, str] = {
    "conflict_prediction": "pr-conflict-guard.yml",
    "runtime_merge_queue": "governed-merge-queue.yml",
    "preview_environment": "preview-environment-contract.yml",
    "governed_pr_automation": "governed-pr-automation.yml",
    "predictive_regression": "predictive-regression-guard.yml",
    "continuous_trilha_d_monitoring": "trilha-d-qualidade-governanca.yml",
    "pr_evidence_gate": "pr-evidence-gate.yml",
}

TRILHA_D_WORKFLOW_EVIDENCE_IDS = frozenset({"continuous_trilha_d_monitoring", "predictive_regression"})


def resolve_governance_next_increment(repo_root: Path | None = None) -> str:
    root = repo_root or Path(__file__).resolve().parents[1]
    history_json = root / "docs/ops-dashboard/data/trilha-d-history.json"
    index_html = root / "docs/ops-dashboard/index.html"
    monitoramento_view = root / "frontend/src/views/MonitoramentoOperacionalView.vue"
    workflow = root / ".github/workflows/trilha-d-qualidade-governanca.yml"
    if not history_json.exists() or not index_html.exists() or not monitoramento_view.exists() or not workflow.exists():
        return NEXT_INCREMENT_AFTER_DEEP_LINKS
    html_text = index_html.read_text(encoding="utf-8")
    view_text = monitoramento_view.read_text(encoding="utf-8")
    workflow_text = workflow.read_text(encoding="utf-8")
    if "artifact-ingestion-enabled" not in html_text or "artifact_ingestion_enabled" not in view_text:
        return NEXT_INCREMENT_AFTER_DEEP_LINKS
    if "--ingest-report" not in workflow_text:
        return NEXT_INCREMENT_AFTER_DEEP_LINKS
    try:
        payload = json.loads(history_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return NEXT_INCREMENT_AFTER_DEEP_LINKS
    summary = payload.get("summary") or {}
    if summary.get("artifact_ingestion_enabled"):
        index_html = root / "docs/ops-dashboard/index.html"
        workflow = root / ".github/workflows/trilha-d-qualidade-governanca.yml"
        monitoring_json = root / "docs/ops-dashboard/data/continuous-trilha-d-monitoring.json"
        if (
            index_html.exists()
            and workflow.exists()
            and monitoring_json.exists()
            and "continuous-monitoring-enabled" in index_html.read_text(encoding="utf-8")
            and "build_continuous_trilha_d_monitoring.py" in workflow.read_text(encoding="utf-8")
        ):
            if coverage_targeted_surface_ready(root):
                governance_index = root / "docs/ops-dashboard/data/governance-evidence-index.json"
                if governance_index.exists():
                    try:
                        governance_payload = json.loads(governance_index.read_text(encoding="utf-8"))
                        if governance_workflow_deep_links_ready(governance_payload.get("evidence") or []):
                            return NEXT_INCREMENT_AFTER_DEEP_LINKS
                    except json.JSONDecodeError:
                        pass
                return NEXT_INCREMENT_AFTER_COVERAGE_TARGETED
            return NEXT_INCREMENT_AFTER_CONTINUOUS_MONITORING
        return NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION
    next_increment = summary.get("next_increment")
    if next_increment == NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION:
        return NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION
    if next_increment == NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD:
        return NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD
    return NEXT_INCREMENT_AFTER_DEEP_LINKS


def workflow_runs_url(workflow_file: str) -> str:
    return f"https://github.com/{REPO}/actions/workflows/{workflow_file}"


def workflow_run_url(workflow_file: str, run_id: str | int | None) -> str:
    run = str(run_id or "").strip()
    if run.isdigit():
        return f"https://github.com/{REPO}/actions/runs/{run}"
    return workflow_runs_url(workflow_file)


def load_trilha_d_latest_run_id(history_path: Path | None = None) -> str | None:
    path = history_path or Path(DEFAULT_TRILHA_D_HISTORY)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    history = payload.get("history") or []
    if not history:
        return None
    for entry in reversed(history):
        run_id = entry.get("run_id")
        if isinstance(run_id, str | int) and str(run_id).isdigit():
            return str(run_id)
        workflow_run_url_value = entry.get("workflow_run_url")
        if isinstance(workflow_run_url_value, str) and "/actions/runs/" in workflow_run_url_value:
            candidate = workflow_run_url_value.rstrip("/").split("/")[-1]
            if candidate.isdigit():
                return candidate
    return None


def enrich_links(
    workflow_file: str,
    *,
    source: str | None = None,
    run_id: str | int | None = None,
) -> dict[str, str]:
    links = {
        "workflow": workflow_runs_url(workflow_file),
        "workflow_runs": workflow_runs_url(workflow_file),
        "latest_run": workflow_run_url(workflow_file, run_id),
    }
    if source:
        links["source"] = source
    if run_id and str(run_id).isdigit():
        links["deep_link_type"] = "workflow_run"
    else:
        links["deep_link_type"] = "workflow_list"
    return links


def enrich_governance_workflow_deep_links(
    items: list[dict[str, Any]],
    *,
    trilha_d_run_id: str | int | None = None,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        copy = dict(item)
        evidence_id = str(copy.get("id") or "")
        workflow_file = WORKFLOW_FILE_BY_EVIDENCE_ID.get(evidence_id)
        links = dict(copy.get("links") or {})
        if workflow_file:
            run_id = trilha_d_run_id if evidence_id in TRILHA_D_WORKFLOW_EVIDENCE_IDS else None
            source = links.get("source")
            copy["links"] = enrich_links(workflow_file, source=source, run_id=run_id)
        enriched.append(copy)
    return enriched


def governance_workflow_deep_links_ready(items: list[dict[str, Any]]) -> bool:
    if not items:
        return False
    resolved = 0
    for item in items:
        if not item.get("dashboard_ready"):
            continue
        latest_run = (item.get("links") or {}).get("latest_run")
        if isinstance(latest_run, str) and "/actions/runs/" in latest_run:
            resolved += 1
    return resolved >= 2


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
            "id": "continuous_trilha_d_monitoring",
            "title": "Continuous Trilha D Monitoring",
            "workflow": "Trilha D — Qualidade e Governança",
            "script": "scripts/build_continuous_trilha_d_monitoring.py",
            "artifact": "continuous-trilha-d-monitoring-evidence",
            "json_path": "artifacts/trilha-d-qualidade-governanca/continuous-trilha-d-monitoring.json",
            "status": "dry_run",
            "dashboard_ready": True,
            "drilldown_fields": [
                "state",
                "monitoring_enabled",
                "regression_alert",
                "alerts_active",
                "alerts",
                "signals",
            ],
            "links": enrich_links(
                "trilha-d-qualidade-governanca.yml",
                source=f"https://github.com/{REPO}/blob/main/scripts/build_continuous_trilha_d_monitoring.py",
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


def build_payload(
    *,
    trilha_d_run_id: str | int | None = None,
    trilha_d_history: Path | None = None,
) -> dict[str, Any]:
    run_id = trilha_d_run_id if trilha_d_run_id is not None else load_trilha_d_latest_run_id(trilha_d_history)
    items = enrich_governance_workflow_deep_links(evidence_items(), trilha_d_run_id=run_id)
    implemented = sum(1 for item in items if item["status"] in {"implemented", "dry_run"})
    dashboard_ready = sum(1 for item in items if item["dashboard_ready"])
    score = round((implemented / len(items)) * 70 + (dashboard_ready / len(items)) * 30)
    deep_links_ready = governance_workflow_deep_links_ready(items)

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
            "governance_deep_links_enabled": deep_links_ready,
            "workflow_run_deep_links_resolved": sum(
                1
                for item in items
                if isinstance((item.get("links") or {}).get("latest_run"), str)
                and "/actions/runs/" in item["links"]["latest_run"]
            ),
            "next_increment": (
                NEXT_INCREMENT_AFTER_DEEP_LINKS
                if deep_links_ready
                else resolve_governance_next_increment()
            ),
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
            "refresh_strategy": (
                "workflow_run_deep_links_enabled"
                if deep_links_ready
                else "workflow_runs_deep_links_enabled"
            ),
        },
    }


def write_payload(
    output_path: str,
    *,
    trilha_d_run_id: str | int | None = None,
    trilha_d_history: Path | None = None,
) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(trilha_d_run_id=trilha_d_run_id, trilha_d_history=trilha_d_history)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera governance-evidence-index.json para o dashboard operacional.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--trilha-d-history", default=DEFAULT_TRILHA_D_HISTORY)
    parser.add_argument("--github-run-id", help="Run ID do workflow Trilha D para deep links")
    parser.add_argument("--json", action="store_true", help="Imprime o payload gerado")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = write_payload(
        args.output,
        trilha_d_run_id=args.github_run_id,
        trilha_d_history=Path(args.trilha_d_history),
    )
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"governance_evidence_score={payload['governance_evidence_score']} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
