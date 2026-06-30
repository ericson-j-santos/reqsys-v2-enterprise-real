#!/usr/bin/env python3
"""Build Trilha D History Index.

Gera um JSON estático consumível pelo dashboard operacional com histórico,
tendência e regressão das dimensões da Trilha D.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_OUTPUT = "docs/ops-dashboard/data/trilha-d-history.json"
REFRESH_STRATEGY_ARTIFACT = "artifact_ingestion_on_trilha_d_consolidate"
REFRESH_STRATEGY_STATIC = "static_json_until_artifact_ingestion_is_enabled"
NEXT_INCREMENT_AFTER_INGESTION = "consolidate_operational_pareto_cycle"
NEXT_INCREMENT_AFTER_PARETO_DASHBOARD = "predictive_regression_gate"
NEXT_INCREMENT_AFTER_PREDICTIVE_DASHBOARD = "coverage_targeted_tests"
NEXT_INCREMENT_AFTER_COVERAGE_TARGETED = "link_governance_cards_to_latest_workflow_runs"
NEXT_INCREMENT_AFTER_GOVERNANCE_DEEP_LINKS = "dashboard_trilha_d_history_card"
NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD = "artifact_ingestion_refresh"
NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION = "continuous_trilha_d_monitoring"
TRILHA_D_WORKFLOW_FILE = "trilha-d-qualidade-governanca.yml"
COVERAGE_TARGETED_CRITICAL_PATH_TESTS = (
    "backend/tests/test_hub_lowcode_service_critical_paths.py",
    "backend/tests/test_wiki_publisher_critical_paths.py",
    "backend/tests/test_power_automate_provisioning_critical_paths.py",
    "backend/tests/test_recomendacoes_ia_critical_paths.py",
)
DIMENSIONS = ("tests", "coverage", "mutation", "contract", "schema", "ci-watch")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def workflow_runs_url() -> str:
    return f"https://github.com/{REPO}/actions/workflows/{TRILHA_D_WORKFLOW_FILE}"


def resolve_history_run_url(run_id: str) -> str:
    run = str(run_id or "").strip()
    if run.isdigit():
        return f"https://github.com/{REPO}/actions/runs/{run}"
    if run.startswith("pr-"):
        return f"https://github.com/{REPO}/pull/{run.removeprefix('pr-')}"
    return workflow_runs_url()


def enrich_history_entry(entry: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(entry)
    enriched["workflow_run_url"] = resolve_history_run_url(str(entry.get("run_id") or ""))
    return enriched


def trend_for(values: list[float]) -> str:
    if len(values) < 2:
        return "stable"
    delta = round(values[-1] - values[0], 2)
    if delta >= 2:
        return "improving"
    if delta <= -2:
        return "regressing"
    return "stable"


def build_sample_history() -> list[dict[str, Any]]:
    return [
        {
            "timestamp": "2026-06-28T00:50:55Z",
            "source": "github_actions_artifact",
            "run_id": "28306826456",
            "state": "failed",
            "average_score": 88.33,
            "dimensions": {
                "tests": {"status": "passed", "score": 100.0},
                "coverage": {"status": "failed", "score": 29.0},
                "mutation": {"status": "passed", "score": 100.0},
                "contract": {"status": "passed", "score": 100.0},
                "schema": {"status": "passed", "score": 100.0},
                "ci-watch": {"status": "passed", "score": 100.0},
            },
            "notes": ["baseline_before_coverage_parser_fix"],
        },
        {
            "timestamp": "2026-06-28T01:39:18Z",
            "source": "merged_pr",
            "run_id": "pr-462",
            "state": "green",
            "average_score": 95.88,
            "dimensions": {
                "tests": {"status": "passed", "score": 100.0},
                "coverage": {"status": "passed", "score": 74.29},
                "mutation": {"status": "passed", "score": 100.0},
                "contract": {"status": "passed", "score": 100.0},
                "schema": {"status": "passed", "score": 100.0},
                "ci-watch": {"status": "passed", "score": 100.0},
            },
            "notes": ["coverage_parser_fix_merged"],
        },
        {
            "timestamp": "2026-06-28T01:43:44Z",
            "source": "merged_pr",
            "run_id": "pr-463",
            "state": "green",
            "average_score": 95.88,
            "dimensions": {
                "tests": {"status": "passed", "score": 100.0},
                "coverage": {"status": "passed", "score": 74.29},
                "mutation": {"status": "passed", "score": 100.0},
                "contract": {"status": "passed", "score": 100.0},
                "schema": {"status": "passed", "score": 100.0},
                "ci-watch": {"status": "passed", "score": 100.0},
            },
            "notes": ["coverage_parser_regression_tests_merged"],
        },
    ]


def history_state_from_report(report_state: str, average_score: float) -> str:
    if report_state == "failed":
        return "failed"
    if report_state == "warning" or average_score < 90:
        return "yellow"
    return "green"


def report_to_history_entry(report: dict[str, Any]) -> dict[str, Any]:
    dimensions: dict[str, Any] = {}
    for item in report.get("dimensions") or []:
        dimension = item.get("dimension")
        if not dimension:
            continue
        dimensions[str(dimension)] = {
            "status": item.get("status", "unknown"),
            "score": float(item.get("score") or 0.0),
        }

    average_score = round(float(report.get("average_score") or 0.0), 2)
    report_state = str(report.get("state") or "unknown")
    notes: list[str] = []
    if report.get("decision"):
        notes.append(str(report["decision"]))
    if report.get("correlation_id"):
        notes.append(f"correlation_id={report['correlation_id']}")

    return {
        "timestamp": report.get("generated_at") or utc_now(),
        "source": "github_actions_artifact",
        "run_id": str(report.get("run_id") or ""),
        "workflow_run_url": resolve_history_run_url(str(report.get("run_id") or "")),
        "state": history_state_from_report(report_state, average_score),
        "average_score": average_score,
        "dimensions": dimensions,
        "notes": notes,
    }


def load_history_from_output(output_path: str | Path) -> list[dict[str, Any]]:
    path = Path(output_path)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    history = payload.get("history")
    return list(history) if isinstance(history, list) else []


def merge_history(
    existing: list[dict[str, Any]],
    new_entry: dict[str, Any],
    *,
    max_samples: int = 50,
) -> list[dict[str, Any]]:
    run_id = str(new_entry.get("run_id") or "")
    filtered = [item for item in existing if str(item.get("run_id") or "") != run_id]
    merged = [*filtered, new_entry]
    merged.sort(key=lambda item: str(item.get("timestamp") or ""))
    return merged[-max_samples:]


def dimension_values(history: list[dict[str, Any]], dimension: str) -> list[float]:
    values: list[float] = []
    for item in history:
        dim = item.get("dimensions", {}).get(dimension, {})
        score = dim.get("score")
        if isinstance(score, int | float):
            values.append(float(score))
    return values


def build_dimension_summary(history: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for dimension in DIMENSIONS:
        values = dimension_values(history, dimension)
        last_status = history[-1].get("dimensions", {}).get(dimension, {}).get("status", "unknown") if history else "unknown"
        summary[dimension] = {
            "current_status": last_status,
            "current_score": round(values[-1], 2) if values else None,
            "previous_score": round(values[-2], 2) if len(values) >= 2 else None,
            "delta_from_baseline": round(values[-1] - values[0], 2) if len(values) >= 2 else 0.0,
            "trend": trend_for(values),
            "samples": len(values),
        }
    return summary


def ops_dashboard_pareto_surface_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    index_html = root / "docs/ops-dashboard/index.html"
    if not index_html.exists():
        return False
    text = index_html.read_text(encoding="utf-8")
    required_markers = (
        'id="trilha-d-history-card"',
        'id="operational-pareto-card"',
        "renderOperationalPareto",
        "renderTrilhaDHistory",
    )
    return all(marker in text for marker in required_markers)


def ops_dashboard_predictive_gate_surface_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    index_html = root / "docs/ops-dashboard/index.html"
    gate_json = root / "docs/ops-dashboard/data/predictive-regression-gate.json"
    if not index_html.exists() or not gate_json.exists():
        return False
    text = index_html.read_text(encoding="utf-8")
    required_markers = (
        'id="predictive-regression-card"',
        "renderPredictiveRegressionGate",
        "predictive-regression-gate.json",
    )
    return all(marker in text for marker in required_markers)


def coverage_targeted_critical_paths_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    return all((root / relative_path).exists() for relative_path in COVERAGE_TARGETED_CRITICAL_PATH_TESTS)


def trilha_d_history_dashboard_surface_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    index_html = root / "docs/ops-dashboard/index.html"
    monitoramento_view = root / "frontend/src/views/MonitoramentoOperacionalView.vue"
    history_json = root / "docs/ops-dashboard/data/trilha-d-history.json"
    if not index_html.exists() or not monitoramento_view.exists() or not history_json.exists():
        return False
    html_text = index_html.read_text(encoding="utf-8")
    view_text = monitoramento_view.read_text(encoding="utf-8")
    required_markers = ("workflow_run_url", "Ver execução")
    if not all(marker in html_text or marker in view_text for marker in required_markers):
        return False
    try:
        payload = json.loads(history_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    history = payload.get("history") or []
    return bool(history) and all(isinstance(item.get("workflow_run_url"), str) for item in history)


def governance_deep_links_surface_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    index_html = root / "docs/ops-dashboard/index.html"
    monitoramento_view = root / "frontend/src/views/MonitoramentoOperacionalView.vue"
    governance_index = root / "docs/ops-dashboard/data/governance-evidence-index.json"
    if not index_html.exists() or not monitoramento_view.exists() or not governance_index.exists():
        return False
    html_text = index_html.read_text(encoding="utf-8")
    view_text = monitoramento_view.read_text(encoding="utf-8")
    required_markers = (
        "Última execução",
        "latest_run",
        "Ver workflow runs",
    )
    if not all(marker in html_text or marker in view_text for marker in required_markers):
        return False
    try:
        payload = json.loads(governance_index.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    evidence = payload.get("evidence") or []
    if not evidence:
        return False
    return all(
        isinstance((item.get("links") or {}).get("latest_run"), str) and item.get("dashboard_ready")
        for item in evidence
    )


def artifact_ingestion_surface_ready(repo_root: Path | None = None) -> bool:
    root = repo_root or Path(__file__).resolve().parents[1]
    workflow = root / ".github/workflows/trilha-d-qualidade-governanca.yml"
    index_html = root / "docs/ops-dashboard/index.html"
    monitoramento_view = root / "frontend/src/views/MonitoramentoOperacionalView.vue"
    if not workflow.exists() or not index_html.exists() or not monitoramento_view.exists():
        return False
    workflow_text = workflow.read_text(encoding="utf-8")
    html_text = index_html.read_text(encoding="utf-8")
    view_text = monitoramento_view.read_text(encoding="utf-8")
    required_markers = (
        "Atualizar histórico Trilha D (artifact ingestion)",
        "--ingest-report",
        "artifact-ingestion-enabled",
        "artifact_ingestion_enabled",
    )
    if not all(marker in workflow_text or marker in html_text or marker in view_text for marker in required_markers):
        return False
    return "--ingest-report" in workflow_text and "artifact-ingestion-enabled" in html_text


def resolve_next_increment(*, artifact_ingestion: bool, repo_root: Path | None = None) -> str:
    if not ops_dashboard_pareto_surface_ready(repo_root):
        return NEXT_INCREMENT_AFTER_INGESTION
    if not ops_dashboard_predictive_gate_surface_ready(repo_root):
        return NEXT_INCREMENT_AFTER_PARETO_DASHBOARD
    if not coverage_targeted_critical_paths_ready(repo_root):
        return NEXT_INCREMENT_AFTER_PREDICTIVE_DASHBOARD
    if not governance_deep_links_surface_ready(repo_root):
        return NEXT_INCREMENT_AFTER_COVERAGE_TARGETED
    if not trilha_d_history_dashboard_surface_ready(repo_root):
        return NEXT_INCREMENT_AFTER_GOVERNANCE_DEEP_LINKS
    if not artifact_ingestion:
        return NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD
    if artifact_ingestion_surface_ready(repo_root):
        return NEXT_INCREMENT_AFTER_ARTIFACT_INGESTION
    return NEXT_INCREMENT_AFTER_TRILHA_D_DASHBOARD


def build_payload(
    history: list[dict[str, Any]] | None = None,
    *,
    artifact_ingestion: bool = False,
) -> dict[str, Any]:
    samples = history if history is not None else build_sample_history()
    samples = [enrich_history_entry(item) for item in samples]
    average_values = [float(item["average_score"]) for item in samples if isinstance(item.get("average_score"), int | float)]
    current_score = round(average_values[-1], 2) if average_values else 0.0
    baseline_score = round(average_values[0], 2) if average_values else 0.0
    delta = round(current_score - baseline_score, 2)
    recent = samples[-2:] if len(samples) >= 2 else samples
    state = "green" if current_score >= 90 and recent and all(item.get("state") == "green" for item in recent) else "yellow"

    return {
        "schema_version": "1.0.0",
        "repo": REPO,
        "generated_at": utc_now(),
        "state": state,
        "current_score": current_score,
        "baseline_score": baseline_score,
        "delta_from_baseline": delta,
        "trend": trend_for(average_values),
        "summary": {
            "samples": len(samples),
            "green_samples": sum(1 for item in samples if item.get("state") == "green"),
            "failed_samples": sum(1 for item in samples if item.get("state") == "failed"),
            "next_increment": resolve_next_increment(artifact_ingestion=artifact_ingestion),
            "artifact_ingestion_enabled": artifact_ingestion,
        },
        "links": {
            "actions": workflow_runs_url(),
            "workflow_runs": workflow_runs_url(),
            "latest_run": workflow_runs_url(),
            "source": f"https://github.com/{REPO}/blob/main/scripts/build_trilha_d_history.py",
            "dashboard_data": f"https://github.com/{REPO}/blob/main/docs/ops-dashboard/data/trilha-d-history.json",
        },
        "dimension_summary": build_dimension_summary(samples),
        "history": samples,
        "runtime_dashboard_contract": {
            "card_fields": ["state", "current_score", "trend", "delta_from_baseline", "workflow_run_url"],
            "series_fields": ["timestamp", "average_score", "state", "workflow_run_url"],
            "dimension_fields": ["current_status", "current_score", "trend", "delta_from_baseline"],
            "refresh_strategy": (
                REFRESH_STRATEGY_ARTIFACT
                if artifact_ingestion
                else (
                    "workflow_runs_deep_links_enabled"
                    if trilha_d_history_dashboard_surface_ready()
                    else REFRESH_STRATEGY_STATIC
                )
            ),
        },
    }


def write_payload(
    output_path: str,
    *,
    history: list[dict[str, Any]] | None = None,
    artifact_ingestion: bool = False,
) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(history, artifact_ingestion=artifact_ingestion)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def ingest_report_into_history(
    report_path: str,
    output_path: str,
    *,
    max_samples: int = 50,
) -> dict[str, Any]:
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    existing = load_history_from_output(output_path)
    entry = report_to_history_entry(report)
    history = merge_history(existing, entry, max_samples=max_samples)
    return write_payload(output_path, history=history, artifact_ingestion=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera trilha-d-history.json para o dashboard operacional.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Imprime o payload gerado")
    parser.add_argument("--ingest-report", help="JSON consolidado da Trilha D para append no histórico")
    parser.add_argument("--max-samples", type=int, default=50, help="Máximo de amostras no histórico")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.ingest_report:
        payload = ingest_report_into_history(args.ingest_report, args.output, max_samples=args.max_samples)
    else:
        payload = write_payload(args.output)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"trilha_d_history_state={payload['state']} score={payload['current_score']} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
